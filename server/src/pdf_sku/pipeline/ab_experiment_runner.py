"""
AB 实验：对比 OCR 增强 vs 纯 LLM 的产品区域检测效果。

流程:
  1. 调用 PaddleOCR-VL 获取页面图片块 + 文字块位置与内容
  2. 在页面截图上画带编号彩色框（标注图）
  3. 向 VLM 发送三种变体：
     Variant A: 标注图 + OCR 文字进 prompt
     Variant B: 纯结构化数据（无图）
     Variant C: 仅标注图，无 OCR 文字（当前系统基线）
  4. 返回所有变体结果，供前端对比展示
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import re
import time
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()


# ──────────────────────────── 数据模型 ────────────────────────────

@dataclass
class TextBox:
    bbox: list[float]   # [x0, y0, x1, y1]，像素坐标
    text: str
    label: str = "text"


@dataclass
class ImgBox:
    bbox: list[float]   # [x0, y0, x1, y1]，像素坐标


@dataclass
class OCRResult:
    text_boxes: list[TextBox]
    img_boxes: list[ImgBox]
    width: int
    height: int


@dataclass
class VariantResult:
    name: str
    prompt: str
    response_text: str
    parsed_matches: list[dict]   # [{"product_index": int, "region_index": int, "photo_type": str}]
    latency_ms: float
    input_tokens: int
    output_tokens: int
    used_image: bool
    used_structured_data: bool
    error: str = ""


# ──────────────────────────── OCR 调用 ────────────────────────────

async def call_paddle_ocr_vl(page_bytes: bytes) -> str | None:
    """调用 PaddleOCR-VL API，返回原始 JSONL 字符串。"""
    try:
        import httpx
    except ImportError:
        logger.warning("ab_experiment_httpx_missing")
        return None

    from pdf_sku.settings import settings

    token = settings.ocr_token
    if not token:
        logger.warning("ab_experiment_ocr_no_token")
        return None

    headers = {"Authorization": f"bearer {token}"}
    payload = {
        "model": settings.ocr_model,
        "optionalPayload": json.dumps({
            "useDocOrientationClassify": False,
            "useDocUnwarping": False,
            "useChartRecognition": False,
        }),
    }

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            settings.ocr_job_url,
            headers=headers,
            data=payload,
            files={"file": ("page.png", page_bytes, "image/png")},
        )
        resp.raise_for_status()
        job_id = resp.json()["data"]["jobId"]
        logger.info("ab_ocr_job_submitted", job_id=job_id)

        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            poll = await client.get(f"{settings.ocr_job_url}/{job_id}", headers=headers)
            poll.raise_for_status()
            data = poll.json()["data"]
            state = data["state"]
            if state == "done":
                jsonl_url = data["resultUrl"]["jsonUrl"]
                break
            elif state == "failed":
                error_msg = data.get("errorMsg", "unknown")
                logger.warning("ab_ocr_job_failed", error=error_msg)
                return None
            await asyncio.sleep(2)
        else:
            logger.warning("ab_ocr_job_timeout")
            return None

        result_resp = await client.get(jsonl_url)
        result_resp.raise_for_status()
        return result_resp.text


def parse_ocr_result(jsonl_text: str) -> OCRResult | None:
    """解析 PaddleOCR-VL JSONL → OCRResult。"""
    for line in jsonl_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            result = json.loads(line)["result"]
        except (json.JSONDecodeError, KeyError):
            continue
        for layout_res in result.get("layoutParsingResults", []):
            pruned = layout_res.get("prunedResult", {})
            width = pruned.get("width", 0)
            height = pruned.get("height", 0)
            text_boxes: list[TextBox] = []
            img_boxes: list[ImgBox] = []
            for blk in pruned.get("parsing_res_list", []):
                label = blk.get("block_label", "")
                bbox = blk.get("block_bbox", [])
                if not bbox or len(bbox) != 4:
                    continue
                if label == "image":
                    img_boxes.append(ImgBox(bbox=list(bbox)))
                else:
                    # 去除 block_content 中的 HTML 标签
                    raw = blk.get("block_content", "")
                    clean = re.sub(r"<[^>]+>", "", raw).strip()
                    if clean:
                        text_boxes.append(TextBox(bbox=list(bbox), text=clean, label=label))
            return OCRResult(
                text_boxes=text_boxes,
                img_boxes=img_boxes,
                width=int(width),
                height=int(height),
            )
    return None


# ──────────────────────────── 标注图生成 ────────────────────────────

_BOX_COLORS = [
    (255, 80, 80),    # 红
    (80, 160, 255),   # 蓝
    (80, 200, 80),    # 绿
    (255, 180, 0),    # 橙
    (200, 80, 200),   # 紫
    (0, 200, 200),    # 青
    (255, 100, 150),  # 粉
    (140, 100, 255),  # 紫蓝
]


def annotate_img_boxes(
    page_bytes: bytes,
    img_boxes: list[ImgBox],
    text_boxes: list[TextBox] | None = None,
) -> bytes:
    """在图片上画标注框，返回 JPEG bytes。

    - img_boxes: 彩色实线框 + 编号（OCR 检测到的图片块，作为候选区域）
    - text_boxes: 黄色虚线框（OCR 检测到的文字块，辅助空间定位）
    """
    from PIL import Image as PILImage, ImageDraw, ImageFont

    img = PILImage.open(io.BytesIO(page_bytes)).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")

    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 12)
    except Exception:
        font = ImageFont.load_default()
        font_small = font

    # 先画 text_boxes（黄色虚线框，画在 img_boxes 下面）
    if text_boxes:
        for tb in text_boxes:
            x0, y0, x1, y1 = [int(v) for v in tb.bbox]
            # 虚线效果：画4条短线段模拟虚线边框
            dash_color = (255, 220, 0, 160)
            for xi in range(x0, x1, 8):
                draw.line([(xi, y0), (min(xi + 4, x1), y0)], fill=dash_color, width=1)
                draw.line([(xi, y1), (min(xi + 4, x1), y1)], fill=dash_color, width=1)
            for yi in range(y0, y1, 8):
                draw.line([(x0, yi), (x0, min(yi + 4, y1))], fill=dash_color, width=1)
                draw.line([(x1, yi), (x1, min(yi + 4, y1))], fill=dash_color, width=1)
            # 截断文字标签（最多 20 字符）
            label_text = tb.text[:20] + ("…" if len(tb.text) > 20 else "")
            draw.text((x0 + 2, y0 + 1), label_text, fill=(255, 220, 0, 200), font=font_small)

    # 再画 img_boxes（彩色实线框 + 编号，覆盖在文字框上面）
    for idx, box in enumerate(img_boxes):
        x0, y0, x1, y1 = [int(v) for v in box.bbox]
        color = _BOX_COLORS[idx % len(_BOX_COLORS)]
        draw.rectangle([x0, y0, x1, y1], fill=(*color, 40), outline=(*color, 220), width=3)
        label = str(idx)
        lx, ly = x0 + 4, y0 + 4
        draw.rectangle([lx - 2, ly - 2, lx + 24, ly + 24], fill=(*color, 220))
        draw.text((lx, ly), label, fill=(255, 255, 255), font=font)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


# ──────────────────────────── VLM 调用 ────────────────────────────

def _vlm_config() -> tuple[str, str, str]:
    """返回 (api_key, api_base, model)。"""
    from pdf_sku.settings import settings
    provider = settings.default_llm_client.lower() if settings.default_llm_client else ""
    if "qwen" in provider:
        return settings.qwen_api_key, settings.qwen_api_base, settings.qwen_model
    # 默认 gemini
    return settings.gemini_api_key, settings.gemini_api_base, settings.gemini_model


async def call_vlm(prompt: str, images: list[bytes] | None = None) -> dict:
    """调用 VLM，返回 {content, input_tokens, output_tokens, latency_ms}。"""
    try:
        import httpx
    except ImportError:
        return {"content": "", "input_tokens": 0, "output_tokens": 0, "latency_ms": 0.0, "error": "httpx not installed"}

    api_key, api_base, model = _vlm_config()
    if not api_key:
        return {"content": "", "input_tokens": 0, "output_tokens": 0, "latency_ms": 0.0, "error": "_API_KEY not configured in .env"}

    base = (api_base or "https://generativelanguage.googleapis.com").rstrip("/")
    url = f"{base}/v1/chat/completions"

    content_parts: list[dict] = []
    if images:
        for img_bytes in images:
            b64 = base64.b64encode(img_bytes).decode()
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })
    content_parts.append({"type": "text", "text": prompt})

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content_parts}],
    }

    t0 = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
            )
        resp.raise_for_status()
        data = resp.json()
        latency_ms = (time.monotonic() - t0) * 1000
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = data.get("usage", {})
        return {
            "content": content,
            "input_tokens": usage.get("prompt_tokens", 0),
            "output_tokens": usage.get("completion_tokens", 0),
            "latency_ms": latency_ms,
            "error": "",
        }
    except Exception as e:
        latency_ms = (time.monotonic() - t0) * 1000
        logger.warning("ab_vlm_call_failed", error=str(e))
        return {"content": "", "input_tokens": 0, "output_tokens": 0, "latency_ms": latency_ms, "error": str(e)}


def parse_vlm_response(text: str) -> list[dict]:
    """从 VLM 响应中解析 JSON 数组。"""
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return []


# ──────────────────────────── Prompt 构建 ────────────────────────────

def _product_list_str(products: list[dict]) -> str:
    lines = []
    for i, p in enumerate(products):
        model = p.get("model", "")
        name = p.get("name", "")
        if model and name:
            lines.append(f"{i}. {model} - {name}")
        elif model:
            lines.append(f"{i}. {model}")
        else:
            lines.append(f"{i}. {name or f'Product {i}'}")
    return "\n".join(lines)


def _response_rules(n_products: int, n_regions: int) -> str:
    return (
        "Return a JSON array:\n"
        '[{"product_index": 0, "region_index": 2, "photo_type": "product_photo"}, ...]\n\n'
        "RULES:\n"
        f"1. product_index: 0-based (0 to {n_products - 1})\n"
        f"2. region_index: the numbered box on the image (0 to {n_regions - 1})\n"
        '3. photo_type: "product_photo" (clean bg) or "lifestyle_photo" (room scene)\n'
        "4. Every product must have exactly one \"product_photo\"\n"
        "5. Respond ONLY with the JSON array, no other text"
    )


async def _run_variant(
    name: str,
    prompt: str,
    images: list[bytes] | None,
    used_image: bool,
    used_structured_data: bool,
) -> VariantResult:
    result = await call_vlm(prompt, images)
    matches = parse_vlm_response(result.get("content", ""))
    return VariantResult(
        name=name,
        prompt=prompt,
        response_text=result.get("content", ""),
        parsed_matches=matches,
        latency_ms=result.get("latency_ms", 0.0),
        input_tokens=result.get("input_tokens", 0),
        output_tokens=result.get("output_tokens", 0),
        used_image=used_image,
        used_structured_data=used_structured_data,
        error=result.get("error", ""),
    )


# ──────────────────────────── 三种变体 ────────────────────────────

async def run_variant_a(
    annotated_bytes: bytes,
    img_boxes: list[ImgBox],
    text_boxes: list[TextBox],
    products: list[dict],
    page_w: int,
    page_h: int,
) -> VariantResult:
    """Variant A: 标注图 + OCR 图框位置 + OCR 文字进 prompt。"""
    n_regions = len(img_boxes)
    n_products = len(products)

    # img_boxes 坐标（编号对应标注图上的彩色框）
    region_lines = []
    for i, box in enumerate(img_boxes):
        x0, y0, x1, y1 = [int(v) for v in box.bbox]
        region_lines.append(f"  {i}: [{x0},{y0},{x1},{y1}]")
    regions_str = "\n".join(region_lines)

    # text_boxes 坐标 + 内容
    ocr_lines = []
    for tb in text_boxes:
        bbox_str = "[{},{},{},{}]".format(*[int(v) for v in tb.bbox])
        ocr_lines.append(f"  {bbox_str} \"{tb.text}\"")
    ocr_text = "\n".join(ocr_lines) if ocr_lines else "  (no text detected)"

    prompt = (
        f"This furniture catalog page has {n_regions} candidate image regions marked with "
        f"colored numbered boxes (0 to {n_regions - 1}).\n\n"
        f"Image region bboxes (format: index: [x0,y0,x1,y1], pixel coords):\n"
        f"{regions_str}\n\n"
        f"OCR text blocks (format: [x0,y0,x1,y1] \"text\"):\n"
        f"{ocr_text}\n\n"
        f"The following {n_products} products have been identified:\n"
        f"{_product_list_str(products)}\n\n"
        "Use both the image region bboxes and the OCR text positions to match each "
        "product to its photo panel. Text blocks spatially close to or below an image region "
        "likely describe that product.\n\n"
        + _response_rules(n_products, n_regions)
    )
    return await _run_variant(
        name="A: 标注图+OCR文字",
        prompt=prompt,
        images=[annotated_bytes],
        used_image=True,
        used_structured_data=True,
    )


async def run_variant_b(
    img_boxes: list[ImgBox],
    text_boxes: list[TextBox],
    products: list[dict],
    page_w: int,
    page_h: int,
) -> VariantResult:
    """Variant B: 纯结构化数据，不发图。"""
    n_regions = len(img_boxes)
    n_products = len(products)

    region_lines = []
    for i, box in enumerate(img_boxes):
        x0, y0, x1, y1 = [int(v) for v in box.bbox]
        region_lines.append(f"  {i}: [{x0},{y0},{x1},{y1}]")
    regions_str = "\n".join(region_lines)

    ocr_lines = []
    for tb in text_boxes:
        bbox_str = "[{},{},{},{}]".format(*[int(v) for v in tb.bbox])
        ocr_lines.append(f"  {bbox_str} \"{tb.text}\"")
    ocr_text = "\n".join(ocr_lines) if ocr_lines else "  (no text detected)"

    prompt = (
        f"Analyze a furniture catalog page ({page_w}×{page_h} pixels).\n\n"
        f"Image regions (0 to {n_regions - 1}):\n{regions_str}\n\n"
        f"OCR text blocks (format: [x0,y0,x1,y1] \"text\"):\n{ocr_text}\n\n"
        f"Products:\n{_product_list_str(products)}\n\n"
        "Based on spatial relationships, match each product to its image region.\n\n"
        + _response_rules(n_products, n_regions)
    )
    return await _run_variant(
        name="B: 纯结构化数据",
        prompt=prompt,
        images=None,
        used_image=False,
        used_structured_data=True,
    )


async def run_variant_c(
    annotated_bytes: bytes,
    img_boxes: list[ImgBox],
    products: list[dict],
) -> VariantResult:
    """Variant C: 仅标注图，不附文字（当前系统基线）。"""
    n_regions = len(img_boxes)
    n_products = len(products)

    prompt = (
        f"This furniture catalog page has {n_regions} candidate image regions marked with "
        f"colored numbered boxes (0 to {n_regions - 1}). "
        f"Yellow dashed boxes indicate OCR-detected text areas.\n\n"
        f"The following {n_products} products have been identified:\n"
        f"{_product_list_str(products)}\n\n"
        "For each product, identify which numbered colored region contains its photo panel.\n\n"
        + _response_rules(n_products, n_regions)
    )
    return await _run_variant(
        name="C: 仅标注图(基线)",
        prompt=prompt,
        images=[annotated_bytes],
        used_image=True,
        used_structured_data=False,
    )


# ──────────────────────────── 入口 ────────────────────────────

async def run_ab_experiment(
    screenshot_bytes: bytes,
    products: list[dict],
    vlm_provider: str = "gemini",
) -> dict:
    """
    运行完整 A/B 实验。

    Args:
        screenshot_bytes: 页面截图 PNG/JPEG bytes
        products: [{"model": "A001", "name": "实木沙发"}, ...]
        vlm_provider: "gemini" | "qwen"（当前仅用于日志，实际由 settings 控制）

    Returns:
        {
          "image_size": {"width": int, "height": int},
          "products": [...],
          "ocr": {
            "text_boxes": [{"bbox": [...], "text": "...", "label": "..."}],
            "img_boxes":  [{"bbox": [...]}],
            "page_size":  {"width": int, "height": int},
          },
          "variants": [
            {
              "name": "A: ...",
              "matches": [...],
              "latency_ms": float,
              "input_tokens": int,
              "output_tokens": int,
              "used_image": bool,
              "used_structured_data": bool,
              "error": str,
            }, ...
          ]
        }
    """
    from PIL import Image as PILImage

    pil = PILImage.open(io.BytesIO(screenshot_bytes))
    img_w, img_h = pil.size

    # 1. 调用 OCR
    logger.info("ab_experiment_start", products=len(products), img=f"{img_w}x{img_h}")
    jsonl_text = await call_paddle_ocr_vl(screenshot_bytes)
    if jsonl_text is None:
        return {"error": "OCR-VL 调用失败"}

    ocr = parse_ocr_result(jsonl_text)
    if ocr is None:
        return {"error": "OCR-VL 结果解析失败"}

    if not ocr.img_boxes:
        return {"error": "OCR-VL 未检测到任何图片块，无法进行实验"}

    # 2. 生成标注图（彩色框=img_boxes，黄色虚线框=text_boxes）
    annotated = annotate_img_boxes(screenshot_bytes, ocr.img_boxes, ocr.text_boxes)

    page_w = ocr.width or img_w
    page_h = ocr.height or img_h

    # 3. 并发运行三个变体
    results = await asyncio.gather(
        run_variant_a(annotated, ocr.img_boxes, ocr.text_boxes, products, page_w, page_h),
        run_variant_b(ocr.img_boxes, ocr.text_boxes, products, page_w, page_h),
        run_variant_c(annotated, ocr.img_boxes, products),
        return_exceptions=True,
    )

    variants_out = []
    for r in results:
        if isinstance(r, Exception):
            variants_out.append({
                "name": "error",
                "matches": [],
                "latency_ms": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "used_image": False,
                "used_structured_data": False,
                "error": str(r),
            })
        else:
            variants_out.append({
                "name": r.name,
                "matches": r.parsed_matches,
                "latency_ms": round(r.latency_ms, 1),
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "used_image": r.used_image,
                "used_structured_data": r.used_structured_data,
                "error": r.error,
                "prompt": r.prompt,
                "response_text": r.response_text,
            })

    return {
        "image_size": {"width": img_w, "height": img_h},
        "products": products,
        "ocr": {
            "text_boxes": [
                {"bbox": tb.bbox, "text": tb.text, "label": tb.label}
                for tb in ocr.text_boxes
            ],
            "img_boxes": [{"bbox": ib.bbox} for ib in ocr.img_boxes],
            "page_size": {"width": page_w, "height": page_h},
        },
        "annotated_image_b64": base64.b64encode(annotated).decode(),
        "variants": variants_out,
    }
