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
    markdown_text: str = ""   # OCR 返回的 markdown 全文（汇总所有 layoutParsingResults）


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

async def call_paddle_ocr_vl(
    page_bytes: bytes,
    filename: str = "page.png",
    content_type: str = "image/png",
) -> str | None:
    """调用 PaddleOCR-VL API，返回原始 JSONL 字符串。

    支持发送 PDF 文件（filename="page.pdf", content_type="application/pdf"），
    OCR 对 PDF 的文字识别效果远优于 PNG 截图。
    """
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
            files={"file": (filename, page_bytes, content_type)},
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
    """解析 PaddleOCR-VL JSONL → OCRResult。

    遍历所有 layoutParsingResults（每个代表页面上一个检测区域），
    合并全部 parsing_res_list，确保不遗漏任何文本框或图片框。
    同时汇总所有 layoutParsingResult 的 markdown.text，拼接为完整的文档文本。
    """
    text_boxes: list[TextBox] = []
    img_boxes: list[ImgBox] = []
    width, height = 0, 0
    found_any = False
    markdown_parts: list[str] = []

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
            if not width:
                width = int(pruned.get("width", 0))
                height = int(pruned.get("height", 0))
            for blk in pruned.get("parsing_res_list", []):
                label = blk.get("block_label", "")
                bbox = blk.get("block_bbox", [])
                if not bbox or len(bbox) != 4:
                    continue
                found_any = True
                if label == "image":
                    img_boxes.append(ImgBox(bbox=list(bbox)))
                else:
                    # 去除 block_content 中的 HTML 标签，并清理 LaTeX 数学格式
                    raw = blk.get("block_content", "")
                    clean = re.sub(r"<[^>]+>", "", raw).strip()
                    # PaddleOCR-VL 对 # 号有时输出 LaTeX 上标格式 $ ^{\#} $，统一转回 #
                    clean = re.sub(r"\s*\$\s*\^\{?\\#\}?\s*\$", "#", clean)
                    # 清理其余孤立的 $ 符号（可能是 LaTeX 残留）
                    clean = re.sub(r"\s*\$\s*", "", clean).strip()
                    if clean:
                        text_boxes.append(TextBox(bbox=list(bbox), text=clean, label=label))
            # 提取 markdown 全文（OCR 对 PDF 输入时，此字段内容最丰富）
            md_text = layout_res.get("markdown", {}).get("text", "")
            if md_text.strip():
                markdown_parts.append(md_text.strip())

    if not found_any:
        return None
    return OCRResult(
        text_boxes=text_boxes,
        img_boxes=img_boxes,
        width=width,
        height=height,
        markdown_text="\n\n".join(markdown_parts),
    )


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


async def call_vlm(prompt: str, images: list[bytes] | None = None, _retries: int = 2) -> dict:
    """调用 VLM，返回 {content, input_tokens, output_tokens, latency_ms}。

    _retries: 失败后最多重试次数（每次等待 3s），用于应对偶发的连接断开/服务端错误。
    """
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
    last_error = ""
    for attempt in range(_retries + 1):
        if attempt > 0:
            wait_s = 3 * attempt
            logger.info("ab_vlm_retry", attempt=attempt, wait_s=wait_s)
            await asyncio.sleep(wait_s)
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
            last_error = str(e)
            logger.warning("ab_vlm_call_failed", attempt=attempt, error=last_error)

    latency_ms = (time.monotonic() - t0) * 1000
    return {"content": "", "input_tokens": 0, "output_tokens": 0, "latency_ms": latency_ms, "error": last_error}


def parse_vlm_response(text: str) -> list[dict]:
    """从 VLM 响应中解析 JSON 数组。

    LLM 常以 ```json ... ``` 代码块或纯文本形式返回，此函数均可处理。
    使用非贪婪匹配，避免跨越多个 [...] 块导致 JSON 解析失败。
    """
    if not text:
        return []
    # 优先尝试从 markdown 代码块中提取（```json ... ``` 或 ``` ... ```）
    code_block = re.search(r"```(?:json)?\s*(\[[\s\S]*?\])\s*```", text)
    if code_block:
        try:
            return json.loads(code_block.group(1))
        except json.JSONDecodeError:
            pass
    # 否则找最后一个完整 JSON 数组（非贪婪从右侧寻找）
    for m in re.finditer(r"\[[\s\S]*?\]", text):
        try:
            parsed = json.loads(m.group(0))
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            continue
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


def _link_text_to_regions(
    img_boxes: list[ImgBox],
    text_boxes: list[TextBox],
) -> dict[int, list[TextBox]]:
    """将每个 text_box 关联到空间上最近的 img_box。

    优先规则：text_box 中心在 img_box 正下方且 X 轴有重叠（文字在图片下方）。
    其次：中心点最近的 img_box。
    """
    import math
    result: dict[int, list[TextBox]] = {i: [] for i in range(len(img_boxes))}
    for tb in text_boxes:
        tb_cx = (tb.bbox[0] + tb.bbox[2]) / 2
        tb_cy = (tb.bbox[1] + tb.bbox[3]) / 2
        best_idx = 0
        best_score = float("inf")
        for i, box in enumerate(img_boxes):
            ix0, iy0, ix1, iy1 = box.bbox
            dist = math.sqrt((tb_cx - (ix0 + ix1) / 2) ** 2 + (tb_cy - (iy0 + iy1) / 2) ** 2)
            # 正下方加分：text 顶部在图片底部附近/以下，且 X 轴有重叠
            x_overlap = max(0.0, min(tb.bbox[2], ix1) - max(tb.bbox[0], ix0))
            x_span = max(1.0, tb.bbox[2] - tb.bbox[0])
            score = dist * 0.3 if (x_overlap / x_span > 0.3 and tb.bbox[1] >= iy0) else dist
            if score < best_score:
                best_score = score
                best_idx = i
        result[best_idx].append(tb)
    return result


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
    markdown_text: str = "",
) -> VariantResult:
    """Variant A: 标注图 + 全部 OCR 文字块坐标，由 LLM 根据空间关系提取产品属性。

    发送单张标注图（与 Variant C 相同的图），同时提供全部 OCR 文字块及其坐标。
    LLM 根据图中彩色编号框的位置 + 文字块坐标，判断每个图框对应的文字标签，
    并从中提取产品属性（型号、名称、尺寸等）。
    不依赖 DB 预设商品列表——OCR 检测到多少产品就输出多少。
    """
    n_regions = len(img_boxes)
    n_texts = len(text_boxes)

    # 图框列表：各自编号 0~n_regions-1
    region_lines = []
    for i, box in enumerate(img_boxes):
        x0, y0, x1, y1 = [int(v) for v in box.bbox]
        region_lines.append(f"  {i}: [{x0},{y0},{x1},{y1}]")
    regions_str = "\n".join(region_lines)

    # 文字块列表：编号 0~n_texts-1，含坐标和内容
    text_lines = []
    for j, tb in enumerate(text_boxes):
        x0, y0, x1, y1 = [int(v) for v in tb.bbox]
        text_lines.append(f"  {j}: [{x0},{y0},{x1},{y1}] \"{tb.text}\"")
    texts_str = "\n".join(text_lines) if text_lines else "  (no text detected)"

    prompt = (
        f"This furniture catalog page has {n_regions} image regions (colored numbered boxes "
        f"0 to {n_regions - 1}) and {n_texts} OCR text blocks.\n\n"
        f"Image regions (index: [x0,y0,x1,y1]):\n{regions_str}\n\n"
        f"OCR text blocks (index: [x0,y0,x1,y1] \"text\"):\n{texts_str}\n\n"
        "Task: For each image region, find the OCR text block(s) spatially closest to it "
        "(typically the label directly below or beside the image). Extract product attributes.\n\n"
        "Return a JSON array — one entry per image region that has an associated text label:\n"
        '[{"region_index": 0, "product_name": "床头柜", "model_number": "Y1081#", '
        '"size": "500×400×550mm", "color": "", "photo_type": "product_photo"}, ...]\n\n'
        "RULES:\n"
        f"1. region_index: 0 to {n_regions - 1}\n"
        "2. Extract product_name, model_number, size, color verbatim from nearby OCR text\n"
        '3. photo_type: "product_photo" (white/clean bg) or "lifestyle_photo" (room scene)\n'
        "4. Omit regions that have no nearby text label\n"
        "5. Respond ONLY with the JSON array, no other text"
    )

    return await _run_variant(
        name="A: 标注图+OCR文字块",
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
    pdf_page_bytes: bytes | None = None,
) -> dict:
    """
    运行完整 A/B 实验。

    Args:
        screenshot_bytes: 页面截图 PNG/JPEG bytes（用于生成标注图、作为 LLM 视觉输入）
        products: [{"model": "A001", "name": "实木沙发"}, ...]
        vlm_provider: "gemini" | "qwen"（当前仅用于日志，实际由 settings 控制）
        pdf_page_bytes: 目标页单页 PDF bytes（可选）。若提供，优先用于 OCR——
                        OCR 对 PDF 的文字识别效果远优于 PNG 截图，能获取完整的 markdown 内容。

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
    # 优先用 PDF 做 OCR（识别质量远优于 PNG 截图，可获得完整 markdown 内容）
    if pdf_page_bytes is not None:
        logger.info("ab_experiment_start_pdf", products=len(products), img=f"{img_w}x{img_h}")
        jsonl_text = await call_paddle_ocr_vl(
            pdf_page_bytes, filename="page.pdf", content_type="application/pdf"
        )
        if jsonl_text is None:
            logger.warning("ab_experiment_pdf_ocr_failed_fallback_to_png")
            jsonl_text = await call_paddle_ocr_vl(screenshot_bytes)
    else:
        logger.info("ab_experiment_start", products=len(products), img=f"{img_w}x{img_h}")
        jsonl_text = await call_paddle_ocr_vl(screenshot_bytes)

    if jsonl_text is None:
        return {"error": "OCR-VL 调用失败"}

    ocr = parse_ocr_result(jsonl_text)
    if ocr is None:
        return {"error": "OCR-VL 结果解析失败"}

    if not ocr.img_boxes:
        return {"error": "OCR-VL 未检测到任何图片块，无法进行实验"}

    # 若 OCR 对大图降采样，bbox 坐标需缩放到实际图片坐标空间
    ocr_w = ocr.width or img_w
    ocr_h = ocr.height or img_h
    scale_x = img_w / ocr_w if ocr_w and ocr_w != img_w else 1.0
    scale_y = img_h / ocr_h if ocr_h and ocr_h != img_h else 1.0
    if scale_x != 1.0 or scale_y != 1.0:
        logger.info("ab_experiment_ocr_scale",
                    ocr_size=f"{ocr_w}x{ocr_h}",
                    img_size=f"{img_w}x{img_h}",
                    scale=f"{scale_x:.3f}x{scale_y:.3f}")
        def _scale_bbox(bbox: list[float]) -> list[float]:
            return [bbox[0]*scale_x, bbox[1]*scale_y, bbox[2]*scale_x, bbox[3]*scale_y]
        ocr = OCRResult(
            text_boxes=[TextBox(bbox=_scale_bbox(tb.bbox), text=tb.text, label=tb.label)
                        for tb in ocr.text_boxes],
            img_boxes=[ImgBox(bbox=_scale_bbox(ib.bbox)) for ib in ocr.img_boxes],
            width=img_w,
            height=img_h,
            markdown_text=ocr.markdown_text,
        )

    # 2. 生成标注图（彩色框=img_boxes，黄色虚线框=text_boxes）
    # 注意：annotated 基于原始 screenshot_bytes，但 ocr.img_boxes/text_boxes 已缩放到 img_w×img_h 空间
    annotated = annotate_img_boxes(screenshot_bytes, ocr.img_boxes, ocr.text_boxes)

    # 发送给 LLM 的标注图需缩放到合理尺寸（最大 1600px），防止超出 API 请求体限制
    # 使用较低 JPEG 质量同时减小文件体积
    _MAX_LLM_DIM = 1600
    if img_w > _MAX_LLM_DIM or img_h > _MAX_LLM_DIM:
        _scale = min(_MAX_LLM_DIM / img_w, _MAX_LLM_DIM / img_h)
        _new_w, _new_h = int(img_w * _scale), int(img_h * _scale)
        _pil = PILImage.open(io.BytesIO(annotated)).resize((_new_w, _new_h), PILImage.LANCZOS)
        _buf = io.BytesIO()
        _pil.save(_buf, format="JPEG", quality=80)
        annotated_for_llm = _buf.getvalue()
        logger.info("ab_experiment_annotated_resized",
                    orig=f"{img_w}x{img_h}", resized=f"{_new_w}x{_new_h}")
    else:
        annotated_for_llm = annotated

    page_w = img_w
    page_h = img_h

    # 若 products 为空（DB 无 SKU 且请求体也未传），从 OCR text_boxes 自动构建商品候选列表
    # OCR 文本块是权威来源——每个 text_box 对应页面上一块产品标签文字
    # 注意：换行符替换为空格，防止破坏 _product_list_str 的格式
    if not products and ocr.text_boxes:
        # OCR 噪音过滤：跳过明显非产品的文本块
        _noise_patterns = re.compile(
            r"too blurry|cannot recognize|image quality|recognize.*text|"
            r"^\d{1,3}$|^page\s*\d",  # 纯数字页码、页眉等
            re.IGNORECASE,
        )
        seen_texts: set[str] = set()
        for tb in ocr.text_boxes:
            clean = " ".join(tb.text.strip().split())   # 合并换行 / 多余空白
            if not clean:
                continue
            if _noise_patterns.search(clean):
                logger.debug("ab_experiment_skip_noise_text", text=clean[:60])
                continue
            if clean not in seen_texts:
                seen_texts.add(clean)
                products.append({"model": "", "name": clean})
        logger.info("ab_experiment_products_from_ocr", count=len(products))

    # 3. 依次运行三个变体（避免并发请求触发 API 限流导致连接断开）
    results = []
    for coro in [
        run_variant_a(annotated_for_llm, ocr.img_boxes, ocr.text_boxes, products, page_w, page_h,
                      markdown_text=ocr.markdown_text),
        run_variant_b(ocr.img_boxes, ocr.text_boxes, products, page_w, page_h),
        run_variant_c(annotated_for_llm, ocr.img_boxes, products),
    ]:
        try:
            results.append(await coro)
        except Exception as exc:
            results.append(exc)

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
            "markdown_text": ocr.markdown_text,
            "ocr_input": "pdf" if pdf_page_bytes else "png",
        },
        "annotated_image_b64": base64.b64encode(annotated).decode(),
        "variants": variants_out,
    }
