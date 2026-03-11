"""
PaddleOCR-VL 客户端。

调用远程 OCR API，提交页面截图（PNG bytes），轮询直到完成，
返回 parsing_res_list（含 image/text 块位置和内容）。

凭据从 settings 读取（通过 .env 加载），不在代码中硬编码。
"""
from __future__ import annotations

import asyncio
import json
import time

import structlog

logger = structlog.get_logger()


async def call_ocr_on_image(
    image_bytes: bytes,
    timeout: int | None = None,
    filename: str = "page.png",
    content_type: str = "image/png",
) -> tuple[list[dict], int, int] | None:
    """调用 PaddleOCR-VL API，返回 (parsing_res_list, ocr_width, ocr_height)。

    Args:
        image_bytes: 页面截图的 PNG/JPEG bytes，或单页 PDF bytes。
        timeout: 超时秒数，默认 120。
        filename: 上传文件名，默认 "page.png"。发送 PDF 时传 "page.pdf"。
        content_type: MIME 类型，默认 "image/png"。PDF 时传 "application/pdf"。

    Returns:
        (parsing_res_list, ocr_width, ocr_height)，其中 ocr_width/ocr_height 是
        OCR 实际处理的图片尺寸（可能因降采样而小于原始图片）。
        失败或超时返回 None。
    """
    try:
        import httpx
    except ImportError:
        logger.warning("ocr_client_httpx_missing")
        return None

    from pdf_sku.settings import settings

    token = settings.ocr_token
    if not token:
        logger.warning("ocr_client_no_token", hint="set OCR_TOKEN in .env")
        return None

    _timeout = timeout or 120
    headers = {"Authorization": f"bearer {token}"}
    payload = {
        "model": settings.ocr_model,
        "optionalPayload": json.dumps({
            "useDocOrientationClassify": False,
            "useDocUnwarping": False,
            "useChartRecognition": False,
        }),
    }

    async with httpx.AsyncClient(timeout=_timeout) as client:
        # 1. 提交任务
        resp = await client.post(
            settings.ocr_job_url,
            headers=headers,
            data=payload,
            files={"file": (filename, image_bytes, content_type)},
        )
        resp.raise_for_status()
        job_id = resp.json()["data"]["jobId"]
        logger.info("ocr_job_submitted", job_id=job_id)

        # 2. 轮询直到完成
        deadline = time.monotonic() + _timeout
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
                logger.warning("ocr_job_failed", job_id=job_id, error=error_msg)
                return None
            await asyncio.sleep(2)
        else:
            logger.warning("ocr_job_timeout", job_id=job_id)
            return None

        # 3. 下载并解析 JSONL 结果
        result_resp = await client.get(jsonl_url)
        result_resp.raise_for_status()
        jsonl_text = result_resp.text

    all_parsing_res: list[dict] = []
    ocr_w, ocr_h = 0, 0
    for line in jsonl_text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        result = json.loads(line)["result"]
        for layout_res in result.get("layoutParsingResults", []):
            pruned = layout_res.get("prunedResult", {})
            if not ocr_w:
                ocr_w = int(pruned.get("width", 0))
                ocr_h = int(pruned.get("height", 0))
            all_parsing_res.extend(pruned.get("parsing_res_list", []))

    return all_parsing_res, ocr_w, ocr_h
