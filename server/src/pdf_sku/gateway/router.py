"""
Gateway API 路由。对齐: OpenAPI V2.0 §/jobs + §/uploads + §/dashboard

端点:
- TUS: POST /uploads, PATCH /uploads/{id}, HEAD /uploads/{id}, DELETE /uploads/{id}
- Jobs: POST /jobs, GET /jobs, GET /jobs/{id}, POST /jobs/{id}/cancel, POST /jobs/{id}/requeue
- Pages: GET /jobs/{id}/pages, GET /jobs/{id}/skus, GET /jobs/{id}/evaluation
- SSE: GET /jobs/{id}/events
- Dashboard: GET /dashboard/metrics
"""
from __future__ import annotations
import uuid
import shutil
from pathlib import Path
from typing import Annotated
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Request, Response, Path as PathParam
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy import select, func, desc, delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from pdf_sku.common.dependencies import DBSession, RedisClient
from pdf_sku.common.models import (
    PDFJob,
    Page,
    SKU,
    Evaluation,
    Annotation,
    HumanTask,
    Image,
    SKUImageBinding,
    StateTransition,
)
from pdf_sku.common.enums import (
    JobInternalStatus, JobUserStatus, compute_user_status, ACTION_HINT_MAP,
)
from pdf_sku.common.exceptions import JobNotFoundError, PDFSKUError
from pdf_sku.common.schemas import PaginationMeta, ErrorResponse
from pdf_sku.auth.dependencies import CurrentUser, UploaderUser, AnyUser, AdminUser
from pdf_sku.settings import settings
from pdf_sku.gateway.event_bus import event_bus
import structlog

logger = structlog.get_logger()

router = APIRouter(tags=["gateway"])


# ───────────────────────── DI helpers ─────────────────────────
def get_tus_handler():
    from pdf_sku.gateway._deps import tus_handler
    return tus_handler


def get_job_factory():
    from pdf_sku.gateway._deps import job_factory
    return job_factory


def get_sse_manager():
    from pdf_sku.gateway._deps import sse_manager
    return sse_manager


def get_llm_service():
    from pdf_sku.gateway._deps import llm_service
    return llm_service


# ───────────────────────── TUS 端点 ─────────────────────────

@router.post("/uploads", status_code=201)
async def tus_create(
    request: Request,
    upload_length: int = Header(..., alias="Upload-Length"),
    upload_metadata: str = Header("", alias="Upload-Metadata"),
):
    """TUS Creation — POST /uploads"""
    # 解析 metadata: "filename base64val,filetype base64val"
    import base64
    metadata = {}
    if upload_metadata:
        for pair in upload_metadata.split(","):
            parts = pair.strip().split(" ", 1)
            if len(parts) == 2:
                metadata[parts[0]] = base64.b64decode(parts[1]).decode()
            elif len(parts) == 1:
                metadata[parts[0]] = ""

    handler = get_tus_handler()
    upload_id = await handler.handle_creation(upload_length, metadata)
    return Response(
        status_code=201,
        headers={
            "Location": f"/api/v1/uploads/{upload_id}",
            "Tus-Resumable": "1.0.0",
            "Upload-Expires": "",
        },
    )


@router.head("/uploads/{upload_id}")
async def tus_head(upload_id: str):
    """TUS HEAD — 查询当前 offset"""
    handler = get_tus_handler()
    offset, length = await handler.handle_head(upload_id)
    return Response(
        status_code=200,
        headers={
            "Upload-Offset": str(offset),
            "Upload-Length": str(length),
            "Tus-Resumable": "1.0.0",
            "Cache-Control": "no-store",
        },
    )


@router.patch("/uploads/{upload_id}", status_code=204)
async def tus_patch(
    request: Request,
    upload_id: str,
    upload_offset: int = Header(..., alias="Upload-Offset"),
    upload_checksum: str | None = Header(None, alias="Upload-Checksum"),
    content_type: str = Header("application/offset+octet-stream", alias="Content-Type"),
):
    """TUS PATCH — 写入分片"""
    chunk = await request.body()
    handler = get_tus_handler()
    new_offset, is_complete = await handler.handle_patch(
        upload_id, upload_offset, chunk, upload_checksum
    )
    headers = {
        "Upload-Offset": str(new_offset),
        "Tus-Resumable": "1.0.0",
    }
    return Response(status_code=204, headers=headers)


@router.delete("/uploads/{upload_id}", status_code=204)
async def tus_delete(upload_id: str):
    """TUS Termination — 取消上传"""
    handler = get_tus_handler()
    await handler.handle_delete(upload_id)
    return Response(status_code=204)


# ───────────────────────── Jobs 端点 ─────────────────────────

@router.post("/jobs", status_code=201)
async def create_job(
    request: Request,
    db: DBSession,
    redis: RedisClient,
    user: UploaderUser,
):
    """
    创建 Job。对齐: Gateway 详设 §4.1
    Body: {"upload_id": str, "merchant_id": str, "category"?: str}
    需要 uploader 或 admin 角色。
    """
    body = await request.json()
    upload_id = body.get("upload_id")
    merchant_id = body.get("merchant_id", user.merchant_id or "")
    category = body.get("category")

    if not upload_id or not merchant_id:
        return JSONResponse(status_code=400, content={
            "error_code": "MISSING_FIELDS",
            "message": "upload_id and merchant_id are required",
        })

    # 获取上传文件路径
    from pdf_sku.gateway._deps import tus_store
    meta = await tus_store.get_metadata(upload_id)
    if meta["status"] != "complete":
        return JSONResponse(status_code=400, content={
            "error_code": "UPLOAD_NOT_COMPLETE",
            "message": f"Upload {upload_id} is not yet complete",
        })

    file_path = tus_store.get_file_path(upload_id)
    factory = get_job_factory()
    job = await factory.create_job(
        db=db, redis=redis,
        upload_file_path=file_path,
        filename=meta["filename"],
        merchant_id=merchant_id,
        category=category,
        uploaded_by=f"{user.username} ({str(user.user_id)[:8]})",
    )
    # 注意: job_factory.create_job 内部已 commit，此处无需再次 commit

    # 清理 TUS 元数据 (文件已移走)
    await tus_store.delete(upload_id)

    return {
        "job_id": str(job.job_id),
        "source_file": job.source_file,
        "status": job.status,
        "user_status": job.user_status,
        "action_hint": job.action_hint,
        "total_pages": job.total_pages,
        "blank_pages": job.blank_pages,
        "created_at": job.created_at.isoformat() if job.created_at else None,
    }


@router.get("/jobs")
async def list_jobs(
    db: DBSession,
    status: str | None = Query(None),
    merchant_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """列出 Job (分页)。"""
    query = select(PDFJob).order_by(desc(PDFJob.created_at))
    count_query = select(func.count()).select_from(PDFJob)

    if status:
        query = query.where(PDFJob.user_status == status)
        count_query = count_query.where(PDFJob.user_status == status)
    if merchant_id:
        query = query.where(PDFJob.merchant_id == merchant_id)
        count_query = count_query.where(PDFJob.merchant_id == merchant_id)

    total = (await db.execute(count_query)).scalar() or 0
    jobs = (await db.execute(
        query.offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return {
        "data": [_job_to_dict(j) for j in jobs],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_count": total,
            "total_pages": (total + page_size - 1) // page_size,
        },
    }


@router.get("/jobs/{job_id}")
async def get_job(job_id: uuid.UUID, db: DBSession):
    """获取 Job 详情。"""
    result = await db.execute(select(PDFJob).where(PDFJob.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job {job_id} not found")
    return _job_to_dict(job, detail=True)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: uuid.UUID, db: DBSession):
    """取消 Job。"""
    from pdf_sku.gateway.user_status import update_job_status
    job = await update_job_status(
        db, str(job_id), JobInternalStatus.CANCELLED.value, trigger="user_cancel"
    )
    await db.commit()
    return {"job_id": str(job_id), "status": job.status, "user_status": job.user_status}


@router.post("/jobs/{job_id}/requeue")
async def requeue_job(job_id: uuid.UUID, db: DBSession, redis: RedisClient):
    """手动重提 Job。"""
    from pdf_sku.gateway.user_status import update_job_status
    result = await db.execute(select(PDFJob).where(PDFJob.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job {job_id} not found")

    if job.status not in (JobInternalStatus.ORPHANED.value, JobInternalStatus.EVAL_FAILED.value):
        from pdf_sku.common.exceptions import JobNotOrphanedError
        raise JobNotOrphanedError(f"Job status {job.status} cannot be requeued")

    job = await update_job_status(
        db, str(job_id), JobInternalStatus.UPLOADED.value, trigger="manual_requeue"
    )
    await db.commit()

    # 重新触发评估流程
    await event_bus.publish("JobCreated", {
        "job_id": str(job_id),
        "file_hash": job.file_hash,
        "total_pages": job.total_pages,
        "status": JobInternalStatus.UPLOADED.value,
        "prescan": (job.processing_trace or {}).get("prescan", {}),
        "config_version": job.frozen_config_version or "default",
    })

    return {"job_id": str(job_id), "status": job.status, "user_status": job.user_status}


@router.delete("/ops/jobs/{job_id}")
async def delete_job(job_id: uuid.UUID, db: DBSession):
    """物理删除 Job 及其关联数据。"""
    result = await db.execute(select(PDFJob).where(PDFJob.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job {job_id} not found")

    task_ids = (await db.execute(
        select(HumanTask.task_id).where(HumanTask.job_id == job_id)
    )).scalars().all()

    if task_ids:
        await db.execute(
            delete(StateTransition).where(
                StateTransition.entity_type == "task",
                StateTransition.entity_id.in_([str(tid) for tid in task_ids]),
            )
        )

    await db.execute(delete(StateTransition).where(
        StateTransition.entity_type == "job",
        StateTransition.entity_id == str(job_id),
    ))
    await db.execute(delete(Annotation).where(Annotation.job_id == job_id))
    await db.execute(delete(HumanTask).where(HumanTask.job_id == job_id))
    await db.execute(delete(SKUImageBinding).where(SKUImageBinding.job_id == job_id))
    await db.execute(delete(Image).where(Image.job_id == job_id))
    await db.execute(delete(SKU).where(SKU.job_id == job_id))
    await db.execute(delete(Page).where(Page.job_id == job_id))
    await db.execute(delete(Evaluation).where(Evaluation.job_id == job_id))
    await db.execute(delete(PDFJob).where(PDFJob.job_id == job_id))
    await db.commit()

    job_dir = Path(settings.job_data_dir) / str(job_id)
    if job_dir.exists():
        shutil.rmtree(job_dir, ignore_errors=True)

    return {"job_id": str(job_id), "deleted": True}


@router.post("/ops/jobs/{job_id}/reprocess-ai")
async def reprocess_job_ai(job_id: uuid.UUID, db: DBSession):
    """强制该 Job 全量走 AI 处理。"""
    result = await db.execute(select(PDFJob).where(PDFJob.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job {job_id} not found")

    task_ids = (await db.execute(
        select(HumanTask.task_id).where(HumanTask.job_id == job_id)
    )).scalars().all()

    deleted_tasks = len(task_ids)
    if task_ids:
        await db.execute(
            delete(StateTransition).where(
                StateTransition.entity_type == "task",
                StateTransition.entity_id.in_([str(tid) for tid in task_ids]),
            )
        )

    # 清理人工相关数据
    if task_ids:
        await db.execute(delete(Annotation).where(Annotation.task_id.in_(task_ids)))
    await db.execute(delete(HumanTask).where(HumanTask.job_id == job_id))

    # 清理旧的 SKU 及关联数据，避免重处理后产生重复
    await db.execute(delete(SKUImageBinding).where(SKUImageBinding.job_id == job_id))
    await db.execute(delete(SKU).where(SKU.job_id == job_id))
    await db.execute(delete(Image).where(Image.job_id == job_id))

    # 重置 Job 级计数，清空旧的 blank_pages
    job.total_skus = 0
    job.total_images = 0
    job.blank_pages = []

    await db.execute(
        update(Page)
        .where(Page.job_id == job_id)
        .values(status="PENDING", needs_review=False, sku_count=0)
    )

    await db.commit()

    eval_data = {
        "job_id": str(job_id),
        "route": "AI_ONLY",
        "degrade_reason": None,
        "prescan": {"blank_pages": []},
    }
    await event_bus.publish("EvaluationCompleted", eval_data)

    return {
        "job_id": str(job_id),
        "queued": True,
        "route": "AI_ONLY",
        "deleted_human_tasks": deleted_tasks,
    }


@router.post("/ops/jobs/{job_id}/reprocess-page/{page_number}")
async def reprocess_single_page(
    job_id: uuid.UUID,
    page_number: int,
    db: DBSession,
    request: Request,
):
    """单页重处理: 仅重跑指定页面的 AI 处理。"""
    result = await db.execute(select(PDFJob).where(PDFJob.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job {job_id} not found")

    if page_number < 1 or page_number > job.total_pages:
        return JSONResponse({"error": f"page_number must be 1-{job.total_pages}"}, 400)

    # 清理该页旧数据
    old_skus = (await db.execute(
        select(SKU.sku_id).where(SKU.job_id == job_id, SKU.page_number == page_number)
    )).scalars().all()
    if old_skus:
        await db.execute(delete(SKUImageBinding).where(
            SKUImageBinding.job_id == job_id,
            SKUImageBinding.sku_id.in_(old_skus),
        ))
    await db.execute(delete(SKU).where(
        SKU.job_id == job_id, SKU.page_number == page_number))
    await db.execute(delete(Image).where(
        Image.job_id == job_id, Image.page_number == page_number))
    await db.execute(
        update(Page).where(
            Page.job_id == job_id, Page.page_number == page_number,
        ).values(status="PENDING", needs_review=False, sku_count=0)
    )
    await db.commit()

    # 直接调用 orchestrator 单页处理
    orchestrator = request.app.state.orchestrator
    file_path = orchestrator._resolve_file_path(job)

    async with orchestrator._db_factory() as page_db:
        result = await orchestrator._process_single_page(
            page_db, job, page_number, file_path)
        await orchestrator._on_page_done(page_db, job, page_number, result)
        await page_db.commit()

    return {
        "job_id": str(job_id),
        "page_number": page_number,
        "status": result.status,
        "sku_count": len(result.skus),
    }


# ───────────────────────── Pages / SKUs / Evaluation ─────────────────────────

@router.get("/jobs/{job_id}/pages")
async def get_pages(
    job_id: uuid.UUID, db: DBSession,
    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=200),
):
    """获取 Job 的页面列表。"""
    count = (await db.execute(
        select(func.count()).where(Page.job_id == job_id)
    )).scalar() or 0

    pages = (await db.execute(
        select(Page)
        .where(Page.job_id == job_id)
        .order_by(Page.page_number)
        .offset((page - 1) * page_size).limit(page_size)
    )).scalars().all()

    return {
        "data": [_page_to_dict(p) for p in pages],
        "pagination": {"page": page, "page_size": page_size,
                        "total_count": count, "total_pages": (count + page_size - 1) // page_size},
    }


@router.get("/jobs/{job_id}/pages/{page_number}/screenshot")
async def get_page_screenshot(
    job_id: uuid.UUID,
    db: DBSession,
    page_number: int = PathParam(..., ge=1),
):
    """返回指定页面的截图 (PNG)。"""

    job_result = await db.execute(select(PDFJob).where(PDFJob.job_id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job {job_id} not found")

    page_result = await db.execute(
        select(Page).where(Page.job_id == job_id, Page.page_number == page_number)
    )
    page = page_result.scalar_one_or_none()
    if not page:
        return JSONResponse(status_code=404, content={
            "error_code": "PAGE_NOT_FOUND",
            "message": f"Page {page_number} not found for job {job_id}",
        })

    job_dir = Path(settings.job_data_dir) / str(job_id)
    cache_path = job_dir / "screenshots" / f"page-{page_number}.png"

    # 优先返回已缓存的截图
    if cache_path.exists():
        return FileResponse(str(cache_path), media_type="image/png")

    # 显式指定的截图路径
    if page.screenshot_path:
        explicit = Path(page.screenshot_path)
        if not explicit.is_absolute():
            explicit = job_dir / explicit
        if explicit.exists():
            return FileResponse(str(explicit), media_type="image/png")

    source_pdf = job_dir / "source.pdf"
    if not source_pdf.exists():
        return JSONResponse(status_code=404, content={
            "error_code": "SOURCE_PDF_MISSING",
            "message": f"Source PDF not found for job {job_id}",
        })

    try:
        import fitz

        doc = fitz.open(source_pdf)
        try:
            if page_number < 1 or page_number > doc.page_count:
                return JSONResponse(status_code=404, content={
                    "error_code": "PAGE_OUT_OF_RANGE",
                    "message": f"Page {page_number} is out of range",
                })

            zoom = 150 / 72
            pix = doc[page_number - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            png_bytes = pix.tobytes("png")
        finally:
            doc.close()
    except Exception as e:
        logger.exception(
            "screenshot_render_failed",
            job_id=str(job_id),
            page_number=page_number,
            error=str(e),
        )
        return JSONResponse(status_code=500, content={
            "error_code": "RENDER_FAILED",
            "message": "Failed to render page screenshot",
        })

    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(png_bytes)
    except Exception as e:
        logger.warning(
            "screenshot_cache_failed",
            job_id=str(job_id),
            page_number=page_number,
            error=str(e),
        )

    return Response(content=png_bytes, media_type="image/png")


@router.get("/jobs/{job_id}/images/{image_id}")
async def get_job_image(
    job_id: uuid.UUID,
    image_id: str,
    db: DBSession,
):
    """返回 Job 中提取的图片文件。"""
    result = await db.execute(
        select(Image).where(Image.job_id == job_id, Image.image_id == image_id)
    )
    img = result.scalars().first()
    if not img or not img.extracted_path:
        return JSONResponse(status_code=404, content={
            "error_code": "IMAGE_NOT_FOUND",
            "message": f"Image {image_id} not found",
        })

    job_dir = Path(settings.job_data_dir) / str(job_id)
    file_path = job_dir / img.extracted_path
    if not file_path.exists():
        return JSONResponse(status_code=404, content={
            "error_code": "IMAGE_FILE_MISSING",
            "message": "Image file not found on disk",
        })

    media = "image/jpeg" if img.format == "jpg" else f"image/{img.format or 'jpeg'}"
    return FileResponse(str(file_path), media_type=media)


@router.get("/jobs/{job_id}/pages/{page_number}/detail")
async def get_page_detail(
    job_id: uuid.UUID,
    db: DBSession,
    page_number: int = PathParam(..., ge=1),
):
    """返回页面 + SKU + Images 合并响应。"""
    page_result = await db.execute(
        select(Page).where(Page.job_id == job_id, Page.page_number == page_number)
    )
    pg = page_result.scalar_one_or_none()
    if not pg:
        return JSONResponse(status_code=404, content={
            "error_code": "PAGE_NOT_FOUND",
            "message": f"Page {page_number} not found for job {job_id}",
        })

    skus_result = await db.execute(
        select(SKU).where(
            SKU.job_id == job_id,
            SKU.page_number == page_number,
            SKU.superseded == False,
        ).order_by(SKU.id)
    )
    page_skus = skus_result.scalars().all()

    images_result = await db.execute(
        select(Image).where(
            Image.job_id == job_id,
            Image.page_number == page_number,
        ).order_by(Image.id)
    )
    page_images = images_result.scalars().all()

    # Build SKU → images map via bindings
    sku_ids = [s.sku_id for s in page_skus]
    bindings_map: dict[str, list] = {sid: [] for sid in sku_ids}
    if sku_ids:
        bindings_result = await db.execute(
            select(SKUImageBinding).where(
                SKUImageBinding.job_id == job_id,
                SKUImageBinding.sku_id.in_(sku_ids),
                SKUImageBinding.is_latest == True,
            )
        )
        for b in bindings_result.scalars().all():
            if b.sku_id in bindings_map:
                bindings_map[b.sku_id].append({
                    "image_id": b.image_id,
                    "method": b.binding_method,
                    "confidence": b.binding_confidence,
                    "rank": b.rank,
                })

    return {
        "page": _page_to_dict(pg),
        "skus": [{
            "sku_id": s.sku_id, "page_number": s.page_number,
            "attributes": s.attributes, "status": s.status,
            "validity": s.validity, "attribute_source": s.attribute_source,
            "import_confirmation": s.import_confirmation,
            "source_bbox": s.source_bbox,
            "images": bindings_map.get(s.sku_id, []),
        } for s in page_skus],
        "images": [{
            "image_id": img.image_id,
            "role": img.role,
            "bbox": img.bbox,
            "extracted_path": img.extracted_path,
            "resolution": img.resolution,
            "short_edge": img.short_edge,
            "search_eligible": img.search_eligible,
        } for img in page_images],
    }


@router.get("/jobs/{job_id}/skus")
async def get_skus(
    job_id: uuid.UUID,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    page_number: int | None = Query(None, ge=1),
):
    """获取 Job 的 SKU 列表（可按页面过滤），附带 images。"""

    base_query = select(SKU).where(SKU.job_id == job_id, SKU.superseded == False)
    count_query = select(func.count()).select_from(SKU).where(
        SKU.job_id == job_id, SKU.superseded == False,
    )

    if page_number:
        base_query = base_query.where(SKU.page_number == page_number)
        count_query = count_query.where(SKU.page_number == page_number)

    count = (await db.execute(count_query)).scalar() or 0

    skus = (await db.execute(
        base_query
        .order_by(SKU.page_number, SKU.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )).scalars().all()

    # Fetch bindings for all returned SKUs
    sku_ids = [s.sku_id for s in skus]
    bindings_map: dict[str, list] = {sid: [] for sid in sku_ids}
    if sku_ids:
        bindings_result = await db.execute(
            select(SKUImageBinding).where(
                SKUImageBinding.job_id == job_id,
                SKUImageBinding.sku_id.in_(sku_ids),
                SKUImageBinding.is_latest == True,
            )
        )
        for b in bindings_result.scalars().all():
            if b.sku_id in bindings_map:
                bindings_map[b.sku_id].append({
                    "image_id": b.image_id,
                    "method": b.binding_method,
                    "confidence": b.binding_confidence,
                    "rank": b.rank,
                })

    return {
        "data": [{
            "sku_id": s.sku_id, "page_number": s.page_number,
            "attributes": s.attributes, "status": s.status,
            "validity": s.validity, "attribute_source": s.attribute_source,
            "import_confirmation": s.import_confirmation,
            "source_bbox": s.source_bbox,
            "images": bindings_map.get(s.sku_id, []),
            "product_id": s.product_id,
            "variant_label": s.variant_label,
        } for s in skus],
        "pagination": {"page": page, "page_size": page_size,
                        "total_count": count, "total_pages": (count + page_size - 1) // page_size},
    }


@router.patch("/jobs/{job_id}/skus/{sku_id}")
async def update_sku(
    request: Request,
    job_id: uuid.UUID,
    sku_id: str,
    db: DBSession,
):
    """更新 SKU 属性（支持已完成 Job 的后期修正）。自动记录 Annotation。"""
    body = await request.json()
    attributes = body.get("attributes")
    validity = body.get("validity")
    annotator = body.get("annotator", "")

    result = await db.execute(
        select(SKU).where(
            SKU.job_id == job_id,
            SKU.sku_id == sku_id,
            SKU.superseded == False,
        )
    )
    sku = result.scalar_one_or_none()
    if not sku:
        return JSONResponse(status_code=404, content={
            "error_code": "SKU_NOT_FOUND",
            "message": f"SKU {sku_id} not found in job {job_id}",
        })

    if attributes is not None:
        old_attrs = dict(sku.attributes or {})
        new_attrs = {**old_attrs, **attributes}
        # Compute diff: only changed fields
        diff = {k: {"old": old_attrs.get(k), "new": v}
                for k, v in attributes.items() if old_attrs.get(k) != v}
        if diff:
            sku.attributes = new_attrs
            sku.attribute_source = "HUMAN_CORRECTED"
            db.add(Annotation(
                job_id=job_id,
                page_number=sku.page_number,
                annotator=annotator,
                type="SKU_ATTRIBUTE_CORRECTION",
                payload={"sku_id": sku_id, "old": old_attrs, "new": new_attrs, "diff": diff},
            ))

    if validity is not None and validity != sku.validity:
        old_validity = sku.validity
        sku.validity = validity
        db.add(Annotation(
            job_id=job_id,
            page_number=sku.page_number,
            annotator=annotator,
            type="SKU_VALIDITY_CORRECTION",
            payload={"sku_id": sku_id, "old_validity": old_validity, "new_validity": validity},
        ))

    await db.commit()

    return {
        "sku_id": sku.sku_id,
        "attributes": sku.attributes,
        "validity": sku.validity,
        "attribute_source": sku.attribute_source,
        "status": sku.status,
    }


@router.patch("/jobs/{job_id}/skus/{sku_id}/binding")
async def update_sku_binding(
    request: Request,
    job_id: uuid.UUID,
    sku_id: str,
    db: DBSession,
):
    """替换 SKU 的图片绑定，记录 BINDING_CORRECTION Annotation。"""
    body = await request.json()
    new_image_id = body.get("image_id")
    annotator = body.get("annotator", "")

    if not new_image_id:
        return JSONResponse(status_code=400, content={
            "error_code": "MISSING_IMAGE_ID",
            "message": "image_id is required",
        })

    # Verify SKU exists
    sku_result = await db.execute(
        select(SKU).where(SKU.job_id == job_id, SKU.sku_id == sku_id, SKU.superseded == False)
    )
    sku = sku_result.scalar_one_or_none()
    if not sku:
        return JSONResponse(status_code=404, content={
            "error_code": "SKU_NOT_FOUND",
            "message": f"SKU {sku_id} not found in job {job_id}",
        })

    # Verify target image exists in this job
    img_result = await db.execute(
        select(Image).where(Image.job_id == job_id, Image.image_id == new_image_id)
    )
    if not img_result.scalar_one_or_none():
        return JSONResponse(status_code=404, content={
            "error_code": "IMAGE_NOT_FOUND",
            "message": f"Image {new_image_id} not found in job {job_id}",
        })

    # Get ALL bindings for this SKU (including non-latest, for revision tracking)
    all_bind_result = await db.execute(
        select(SKUImageBinding).where(
            SKUImageBinding.sku_id == sku_id,
            SKUImageBinding.job_id == job_id,
        )
    )
    all_bindings = all_bind_result.scalars().all()
    old_image_ids = [b.image_id for b in all_bindings if b.is_latest]
    max_revision = max((b.revision for b in all_bindings), default=0)

    # Mark all current bindings as not latest
    for b in all_bindings:
        b.is_latest = False

    # Check if binding for new image already exists (reuse row to respect unique constraint)
    existing = next((b for b in all_bindings if b.image_id == new_image_id), None)
    if existing:
        existing.is_latest = True
        existing.binding_method = "human_correction"
        existing.binding_confidence = 1.0
        existing.is_ambiguous = False
        existing.rank = 1
        existing.revision = max_revision + 1
    else:
        db.add(SKUImageBinding(
            sku_id=sku_id,
            image_id=new_image_id,
            job_id=job_id,
            image_role="PRODUCT_MAIN",
            binding_method="human_correction",
            binding_confidence=1.0,
            is_ambiguous=False,
            rank=1,
            revision=max_revision + 1,
            is_latest=True,
        ))

    # Record annotation
    db.add(Annotation(
        job_id=job_id,
        page_number=sku.page_number,
        annotator=annotator,
        type="BINDING_CORRECTION",
        payload={"sku_id": sku_id, "old_image_ids": old_image_ids, "new_image_id": new_image_id},
    ))

    await db.commit()
    return {"sku_id": sku_id, "new_image_id": new_image_id, "old_image_ids": old_image_ids}


@router.post("/jobs/{job_id}/pages/{page_number}/review-complete")
async def mark_review_complete(
    request: Request,
    job_id: uuid.UUID,
    db: DBSession,
    page_number: int = PathParam(..., ge=1),
):
    """标记页面审核完成，记录 PAGE_REVIEW_COMPLETE Annotation。"""
    body = await request.json()
    reviewer = body.get("reviewer", "")
    review_time_sec = body.get("review_time_sec")

    # Find page
    result = await db.execute(
        select(Page).where(Page.job_id == job_id, Page.page_number == page_number)
        .order_by(desc(Page.attempt_no)).limit(1)
    )
    page = result.scalar_one_or_none()
    if not page:
        return JSONResponse(status_code=404, content={
            "error_code": "PAGE_NOT_FOUND",
            "message": f"Page {page_number} not found in job {job_id}",
        })

    if not page.needs_review:
        return JSONResponse(status_code=409, content={
            "error_code": "NOT_IN_REVIEW",
            "message": f"Page {page_number} is not marked for review",
        })

    page.needs_review = False

    db.add(Annotation(
        job_id=job_id,
        page_number=page_number,
        annotator=reviewer,
        type="PAGE_REVIEW_COMPLETE",
        payload={
            "reviewer": reviewer,
            "review_time_sec": review_time_sec,
        },
    ))

    await db.commit()

    # Update job review_pages list
    job_result = await db.execute(select(PDFJob).where(PDFJob.job_id == job_id))
    job = job_result.scalar_one_or_none()
    if job and job.review_pages and page_number in job.review_pages:
        job.review_pages = [p for p in job.review_pages if p != page_number]
        await db.commit()

    return {"page_number": page_number, "needs_review": False}


@router.get("/ops/review-stats")
async def review_stats(
    db: DBSession,
    job_id: str | None = Query(None),
    days: int = Query(30, ge=1, le=365),
):
    """审核统计：按类型聚合 annotation 数据，分析常见修正模式。"""
    from datetime import timedelta

    since = datetime.now(timezone.utc) - timedelta(days=days)
    review_types = [
        "SKU_ATTRIBUTE_CORRECTION",
        "SKU_VALIDITY_CORRECTION",
        "BINDING_CORRECTION",
        "PAGE_REVIEW_COMPLETE",
    ]

    query = (
        select(Annotation.type, func.count().label("count"))
        .where(Annotation.type.in_(review_types), Annotation.annotated_at >= since)
    )
    if job_id:
        query = query.where(Annotation.job_id == uuid.UUID(job_id))
    query = query.group_by(Annotation.type)

    result = await db.execute(query)
    type_counts = {row.type: row.count for row in result.all()}

    # Attribute field correction frequency
    field_freq: dict[str, int] = {}
    if type_counts.get("SKU_ATTRIBUTE_CORRECTION", 0) > 0:
        attr_query = (
            select(Annotation.payload)
            .where(
                Annotation.type == "SKU_ATTRIBUTE_CORRECTION",
                Annotation.annotated_at >= since,
            )
        )
        if job_id:
            attr_query = attr_query.where(Annotation.job_id == uuid.UUID(job_id))
        attr_result = await db.execute(attr_query)
        for row in attr_result.scalars():
            diff = row.get("diff", {}) if isinstance(row, dict) else {}
            for field_name in diff:
                field_freq[field_name] = field_freq.get(field_name, 0) + 1

    return {
        "period_days": days,
        "job_id": job_id,
        "correction_type_counts": type_counts,
        "total_corrections": sum(type_counts.values()),
        "attribute_field_frequency": dict(sorted(field_freq.items(), key=lambda x: -x[1])),
    }


@router.get("/jobs/{job_id}/evaluation")
async def get_evaluation(job_id: uuid.UUID, db: DBSession):
    """获取 Job 的评估结果。"""
    result = await db.execute(select(PDFJob).where(PDFJob.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job {job_id} not found")

    eval_result = await db.execute(
        select(Evaluation).where(Evaluation.file_hash == job.file_hash)
        .order_by(desc(Evaluation.evaluated_at)).limit(1)
    )
    evaluation = eval_result.scalar_one_or_none()
    if not evaluation:
        return JSONResponse(status_code=404, content={
            "error_code": "NOT_EVALUATED", "message": "No evaluation found"})

    return {
        "doc_confidence": evaluation.doc_confidence,
        "route": evaluation.route,
        "route_reason": evaluation.route_reason,
        "dimension_scores": evaluation.dimension_scores,
        "prescan": evaluation.prescan,
        "model_used": evaluation.model_used,
        "evaluated_at": evaluation.evaluated_at.isoformat() if evaluation.evaluated_at else None,
    }


# ───────────────────────── SSE ─────────────────────────

@router.get("/jobs/{job_id}/events")
async def sse_stream(job_id: uuid.UUID, db: DBSession):
    """SSE 事件流。对齐: Gateway 详设 §4.3"""
    # 验证 Job 存在
    result = await db.execute(select(PDFJob.job_id).where(PDFJob.job_id == job_id))
    if not result.scalar_one_or_none():
        raise JobNotFoundError(f"Job {job_id} not found")

    mgr = get_sse_manager()
    return EventSourceResponse(
        mgr.subscribe_job(str(job_id)),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ───────────────────────── Dashboard ─────────────────────────

@router.get("/dashboard/metrics")
async def dashboard_metrics(db: DBSession):
    """仪表盘概览指标 (增强版)。"""
    from pdf_sku.gateway.dashboard import DashboardService
    from datetime import timedelta

    dashboard = DashboardService()
    overview = await dashboard.get_overview(db)

    # 补充今日统计
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    today_jobs = (await db.execute(
        select(func.count()).where(PDFJob.created_at >= today_start)
    )).scalar() or 0

    today_skus = (await db.execute(
        select(func.count()).where(SKU.created_at >= today_start)
    )).scalar() or 0

    return {
        "today_jobs": today_jobs,
        "today_skus": today_skus,
        **overview,
    }


# ───────────────────────── Health ─────────────────────────

@router.get("/health")
async def health(db: DBSession, redis: RedisClient):
    """健康检查。"""
    checks = {}
    try:
        await db.execute(select(func.now()))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"

    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "healthy" if healthy else "degraded", "checks": checks},
    )


# ───────────────────────── OCR Region ─────────────────────────

OCR_REGION_PROMPT = """Extract product attributes from this image region.
Return JSON: {"product_name": "...", "model_number": "...", "price": "...",
"description": "...", "material": "...", "color": "...", "size": "...", "weight": "...", "source_text": "all visible text"}
Only include attributes clearly visible. Use null for missing ones."""


@router.post("/jobs/{job_id}/pages/{page_number}/ocr-region")
async def ocr_region(
    request: Request,
    job_id: uuid.UUID,
    db: DBSession,
    page_number: int = PathParam(..., ge=1),
):
    """OCR 识别页面指定区域的文字，提取商品属性。"""
    body = await request.json()
    bbox = body.get("bbox")
    if not bbox or len(bbox) != 4:
        return JSONResponse(status_code=400, content={
            "error_code": "INVALID_BBOX",
            "message": "bbox must be [x1, y1, x2, y2]",
        })

    llm_service = get_llm_service()
    if llm_service is None:
        return JSONResponse(status_code=503, content={
            "error_code": "LLM_NOT_AVAILABLE",
            "message": "LLM service is not initialized",
        })

    # Get page screenshot PNG bytes
    job_dir = Path(settings.job_data_dir) / str(job_id)
    cache_path = job_dir / "screenshots" / f"page-{page_number}.png"
    png_bytes: bytes | None = None

    if cache_path.exists():
        png_bytes = cache_path.read_bytes()
    else:
        source_pdf = job_dir / "source.pdf"
        if not source_pdf.exists():
            return JSONResponse(status_code=404, content={
                "error_code": "SOURCE_PDF_MISSING",
                "message": f"Source PDF not found for job {job_id}",
            })
        try:
            import fitz
            doc = fitz.open(source_pdf)
            try:
                if page_number < 1 or page_number > doc.page_count:
                    return JSONResponse(status_code=404, content={
                        "error_code": "PAGE_OUT_OF_RANGE",
                        "message": f"Page {page_number} is out of range",
                    })
                zoom = 150 / 72
                pix = doc[page_number - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                png_bytes = pix.tobytes("png")
            finally:
                doc.close()
        except Exception as e:
            logger.exception("ocr_screenshot_failed", error=str(e))
            return JSONResponse(status_code=500, content={
                "error_code": "RENDER_FAILED",
                "message": "Failed to render page for OCR",
            })

    # Crop bbox region using Pillow
    try:
        from PIL import Image as PILImage
        import io

        full_img = PILImage.open(io.BytesIO(png_bytes))
        x1, y1, x2, y2 = [int(v) for v in bbox]
        # Clamp to image bounds
        x1 = max(0, min(x1, full_img.width))
        y1 = max(0, min(y1, full_img.height))
        x2 = max(0, min(x2, full_img.width))
        y2 = max(0, min(y2, full_img.height))
        cropped = full_img.crop((x1, y1, x2, y2))

        # Resize if too large — LLM APIs have image size limits
        MAX_LONG_EDGE = 2048
        w, h = cropped.size
        if max(w, h) > MAX_LONG_EDGE:
            ratio = MAX_LONG_EDGE / max(w, h)
            cropped = cropped.resize(
                (int(w * ratio), int(h * ratio)),
                PILImage.LANCZOS,
            )
            logger.info("ocr_crop_resized",
                        original=f"{w}x{h}",
                        resized=f"{cropped.size[0]}x{cropped.size[1]}")

        buf = io.BytesIO()
        cropped.save(buf, format="PNG")
        crop_bytes = buf.getvalue()
    except Exception as e:
        logger.exception("ocr_crop_failed", error=str(e))
        return JSONResponse(status_code=500, content={
            "error_code": "CROP_FAILED",
            "message": "Failed to crop image region",
        })

    # Call LLM for OCR
    try:
        import json as json_mod
        resp = await llm_service.call_llm(
            operation="ocr_region",
            prompt=OCR_REGION_PROMPT,
            images=[crop_bytes],
        )
        # Parse JSON from response
        try:
            result = json_mod.loads(resp.content)
        except json_mod.JSONDecodeError:
            # Try to extract JSON from markdown code block
            import re
            match = re.search(r"```(?:json)?\s*([\s\S]*?)```", resp.content)
            if match:
                result = json_mod.loads(match.group(1).strip())
            else:
                result = {"source_text": resp.content}

        source_text = result.pop("source_text", "")
        # Remove null values
        attributes = {k: v for k, v in result.items() if v is not None}

        return {"attributes": attributes, "source_text": source_text}

    except Exception as e:
        logger.exception("ocr_llm_failed", error=str(e))
        return JSONResponse(status_code=500, content={
            "error_code": "OCR_FAILED",
            "message": f"OCR extraction failed: {str(e)}",
        })


# ───────────────────────── Crop Image (人工添加/调整子图) ─────────────────────────

@router.post("/jobs/{job_id}/pages/{page_number}/crop-image")
async def crop_image(
    request: Request,
    job_id: uuid.UUID,
    db: DBSession,
    page_number: int = PathParam(..., ge=1),
):
    """从页面截图上裁剪指定区域作为商品子图。

    用途:
    - 人工添加遗漏的商品子图 (mode=add)
    - 调整已有子图的截取范围 (mode=adjust, 传 image_id)

    Body: { "bbox": [x1,y1,x2,y2], "image_id": "可选-更新已有图片", "sku_id": "可选-绑定到SKU" }
    坐标系: 截图像素坐标 (与前端展示的页面截图一致, @150dpi)
    """
    body = await request.json()
    bbox = body.get("bbox")
    if not bbox or len(bbox) != 4:
        return JSONResponse(status_code=400, content={
            "error_code": "INVALID_BBOX",
            "message": "bbox must be [x1, y1, x2, y2]",
        })

    existing_image_id = body.get("image_id")  # 调整模式
    bind_sku_id = body.get("sku_id")          # 可选: 同时绑定到 SKU

    # 验证 job 存在
    job_result = await db.execute(select(PDFJob).where(PDFJob.job_id == job_id))
    job = job_result.scalar_one_or_none()
    if not job:
        raise JobNotFoundError(f"Job {job_id} not found")

    # 获取页面截图
    job_dir = Path(settings.job_data_dir) / str(job_id)
    cache_path = job_dir / "screenshots" / f"page-{page_number}.png"
    png_bytes: bytes | None = None

    if cache_path.exists():
        png_bytes = cache_path.read_bytes()
    else:
        source_pdf = job_dir / "source.pdf"
        if not source_pdf.exists():
            return JSONResponse(status_code=404, content={
                "error_code": "SOURCE_PDF_MISSING",
                "message": f"Source PDF not found for job {job_id}",
            })
        try:
            import fitz
            doc = fitz.open(source_pdf)
            try:
                if page_number < 1 or page_number > doc.page_count:
                    return JSONResponse(status_code=404, content={
                        "error_code": "PAGE_OUT_OF_RANGE",
                        "message": f"Page {page_number} is out of range",
                    })
                zoom = 150 / 72
                pix = doc[page_number - 1].get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                png_bytes = pix.tobytes("png")
            finally:
                doc.close()
        except Exception as e:
            logger.exception("crop_screenshot_failed", error=str(e))
            return JSONResponse(status_code=500, content={
                "error_code": "RENDER_FAILED",
                "message": "Failed to render page screenshot",
            })

    # 裁剪
    try:
        from PIL import Image as PILImage
        import io

        full_img = PILImage.open(io.BytesIO(png_bytes))
        x1, y1, x2, y2 = [int(v) for v in bbox]
        x1 = max(0, min(x1, full_img.width))
        y1 = max(0, min(y1, full_img.height))
        x2 = max(0, min(x2, full_img.width))
        y2 = max(0, min(y2, full_img.height))
        if x2 <= x1 or y2 <= y1:
            return JSONResponse(status_code=400, content={
                "error_code": "INVALID_BBOX",
                "message": "bbox area is zero or negative",
            })
        cropped = full_img.crop((x1, y1, x2, y2))

        buf = io.BytesIO()
        cropped.save(buf, format="JPEG", quality=90)
        crop_bytes = buf.getvalue()
        w, h = cropped.size
    except Exception as e:
        logger.exception("crop_failed", error=str(e))
        return JSONResponse(status_code=500, content={
            "error_code": "CROP_FAILED",
            "message": "Failed to crop image region",
        })

    import hashlib as _hashlib
    img_hash = _hashlib.md5(crop_bytes[:2048]).hexdigest()[:12]

    if existing_image_id:
        # ═══ 调整模式: 更新已有图片 ═══
        result = await db.execute(
            select(Image).where(
                Image.job_id == job_id, Image.image_id == existing_image_id))
        img_row = result.scalars().first()
        if not img_row:
            return JSONResponse(status_code=404, content={
                "error_code": "IMAGE_NOT_FOUND",
                "message": f"Image {existing_image_id} not found",
            })
        # 覆写图片文件
        file_path = job_dir / img_row.extracted_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_bytes(crop_bytes)
        # 更新 DB 元数据
        img_row.bbox = [x1, y1, x2, y2]
        img_row.resolution = [w, h]
        img_row.short_edge = min(w, h)
        img_row.image_hash = img_hash
        img_row.search_eligible = min(w, h) >= 200
        img_row.parser_backend = "manual_crop"
        await db.commit()

        image_id = existing_image_id
        logger.info("image_crop_adjusted",
                     job_id=str(job_id), image_id=image_id,
                     bbox=[x1, y1, x2, y2], size=f"{w}x{h}")
    else:
        # ═══ 添加模式: 创建新图片 ═══
        from nanoid import generate as nanoid
        image_id = f"p{page_number}_manual_{nanoid(size=6)}"
        file_rel = f"images/{image_id}.jpg"
        file_abs = job_dir / file_rel
        file_abs.parent.mkdir(parents=True, exist_ok=True)
        file_abs.write_bytes(crop_bytes)

        db.add(Image(
            image_id=image_id,
            job_id=job_id,
            page_number=page_number,
            role="product_main",
            bbox=[x1, y1, x2, y2],
            extracted_path=file_rel,
            format="jpg",
            resolution=[w, h],
            short_edge=min(w, h),
            image_hash=img_hash,
            search_eligible=min(w, h) >= 200,
            parser_backend="manual_crop",
        ))

        # 如果指定了 sku_id, 同时创建绑定
        if bind_sku_id:
            db.add(SKUImageBinding(
                sku_id=bind_sku_id,
                image_id=image_id,
                job_id=job_id,
                binding_method="manual",
                binding_confidence=1.0,
                rank=1,
            ))

        await db.commit()
        logger.info("image_crop_added",
                     job_id=str(job_id), image_id=image_id,
                     page=page_number, bbox=[x1, y1, x2, y2],
                     size=f"{w}x{h}", sku_id=bind_sku_id)

    return {
        "image_id": image_id,
        "bbox": [x1, y1, x2, y2],
        "resolution": [w, h],
        "short_edge": min(w, h),
        "mode": "adjust" if existing_image_id else "add",
    }


# ───────────────────────── LLM Accounts ─────────────────────────

@router.get("/system/llm-accounts")
async def list_llm_accounts(db: DBSession, _admin: AdminUser):
    """列出所有 LLM 账号（key 脱敏）。"""
    from pdf_sku.llm_adapter.account_service import list_accounts
    accounts = await list_accounts(db)
    return {"accounts": accounts}


@router.post("/system/llm-accounts")
async def create_llm_account(request: Request, db: DBSession, _admin: AdminUser):
    """创建 LLM 账号。"""
    from pdf_sku.llm_adapter.account_service import create_account

    body = await request.json()
    name = body.get("name", "").strip()
    provider_type = body.get("provider_type", "").strip()
    api_base = body.get("api_base", "").strip()
    api_key = body.get("api_key", "").strip()

    if not name or not provider_type or not api_key:
        return JSONResponse(status_code=400, content={
            "error_code": "MISSING_FIELDS",
            "message": "name, provider_type, and api_key are required",
        })

    jwt_secret = settings.jwt_secret_key
    if not jwt_secret:
        return JSONResponse(status_code=500, content={
            "error_code": "NO_SECRET",
            "message": "JWT_SECRET_KEY not configured, cannot encrypt",
        })

    try:
        account = await create_account(db, name, provider_type, api_base, api_key, jwt_secret)
        return {"account": account}
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            return JSONResponse(status_code=409, content={
                "error_code": "DUPLICATE_NAME",
                "message": f"Account name '{name}' already exists",
            })
        raise


@router.delete("/system/llm-accounts/{account_id}")
async def delete_llm_account(account_id: int, db: DBSession, _admin: AdminUser):
    """删除 LLM 账号。"""
    from pdf_sku.llm_adapter.account_service import delete_account
    deleted = await delete_account(db, account_id)
    if not deleted:
        return JSONResponse(status_code=404, content={
            "error_code": "ACCOUNT_NOT_FOUND",
            "message": f"Account {account_id} not found",
        })
    return Response(status_code=204)


# ───────────────────────── Pipeline Concurrency Rules ─────────────────────────

from pdf_sku.pipeline.orchestrator import (
    CONCURRENCY_RULES_KEY, DEFAULT_CONCURRENCY_RULES,
)


@router.get("/system/pipeline-concurrency")
async def get_pipeline_concurrency(request: Request, _admin: AdminUser):
    """获取 Pipeline 并发规则。"""
    redis = getattr(request.app.state, "redis", None)
    if redis:
        try:
            raw = await redis.get(CONCURRENCY_RULES_KEY)
            if raw:
                import json as json_mod
                rules = json_mod.loads(raw)
                return {"rules": rules}
        except Exception:
            pass
    return {"rules": DEFAULT_CONCURRENCY_RULES}


@router.put("/system/pipeline-concurrency")
async def set_pipeline_concurrency(request: Request, _admin: AdminUser):
    """设置 Pipeline 并发规则。"""
    import json as json_mod

    redis = getattr(request.app.state, "redis", None)
    if not redis:
        return JSONResponse(status_code=503, content={
            "error_code": "REDIS_UNAVAILABLE",
            "message": "Redis is not available, cannot persist rules",
        })

    body = await request.json()
    rules = body.get("rules")
    if not rules or not isinstance(rules, list):
        return JSONResponse(status_code=400, content={
            "error_code": "INVALID_RULES",
            "message": "rules must be a non-empty array of {min_pages, concurrency}",
        })
    # Validate each rule
    for rule in rules:
        if not isinstance(rule.get("min_pages"), int) or rule["min_pages"] < 1:
            return JSONResponse(status_code=400, content={
                "error_code": "INVALID_RULE",
                "message": f"min_pages must be a positive integer, got: {rule.get('min_pages')}",
            })
        if not isinstance(rule.get("concurrency"), int) or rule["concurrency"] < 1:
            return JSONResponse(status_code=400, content={
                "error_code": "INVALID_RULE",
                "message": f"concurrency must be a positive integer, got: {rule.get('concurrency')}",
            })
        # provider_name is optional (empty string = global default)
        if "provider_name" in rule and not isinstance(rule["provider_name"], str):
            return JSONResponse(status_code=400, content={
                "error_code": "INVALID_RULE",
                "message": "provider_name must be a string",
            })

    # Sort by min_pages ascending for consistency
    rules = sorted(rules, key=lambda r: r["min_pages"])
    await redis.set(CONCURRENCY_RULES_KEY, json_mod.dumps(rules))
    logger.info("pipeline_concurrency_rules_updated", rules=rules)
    return {"rules": rules}


# ───────────────────────── LLM Provider Config ─────────────────────────

from pdf_sku.llm_adapter.provider_config import (
    LLMProviderConfig,
    DEFAULT_PROVIDER_CONFIGS,
    get_provider_config,
    set_provider_config,
    list_provider_configs,
    get_provider_entries,
    reorder_providers,
    toggle_provider,
    update_provider_entry,
)
from dataclasses import asdict as _asdict


@router.get("/system/llm-provider-configs")
async def get_llm_provider_configs(request: Request, _admin: AdminUser):
    """列出所有 LLM provider 的运行时配置。"""
    redis = getattr(request.app.state, "redis", None)
    configs = await list_provider_configs(redis)
    return {"configs": configs}


@router.put("/system/llm-provider-configs/{provider}")
async def update_llm_provider_config(
    request: Request,
    provider: str,
    _admin: AdminUser,
):
    """更新指定 LLM provider 的运行时配置。"""
    if provider not in DEFAULT_PROVIDER_CONFIGS:
        return JSONResponse(status_code=400, content={
            "error_code": "UNKNOWN_PROVIDER",
            "message": f"Unknown provider: {provider}. Known: {list(DEFAULT_PROVIDER_CONFIGS)}",
        })

    redis = getattr(request.app.state, "redis", None)
    if not redis:
        return JSONResponse(status_code=503, content={
            "error_code": "REDIS_UNAVAILABLE",
            "message": "Redis is not available, cannot persist config",
        })

    body = await request.json()
    current = await get_provider_config(redis, provider)
    updated = LLMProviderConfig(
        timeout_seconds=body.get("timeout_seconds", current.timeout_seconds),
        vlm_timeout_seconds=body.get("vlm_timeout_seconds", current.vlm_timeout_seconds),
        max_retries=body.get("max_retries", current.max_retries),
    )

    # Basic validation
    if updated.timeout_seconds < 1 or updated.vlm_timeout_seconds < 1:
        return JSONResponse(status_code=400, content={
            "error_code": "INVALID_VALUE",
            "message": "timeout values must be >= 1",
        })
    if updated.max_retries < 0 or updated.max_retries > 10:
        return JSONResponse(status_code=400, content={
            "error_code": "INVALID_VALUE",
            "message": "max_retries must be between 0 and 10",
        })

    await set_provider_config(redis, provider, updated)
    logger.info("llm_provider_config_updated", provider=provider,
                timeout=updated.timeout_seconds,
                vlm_timeout=updated.vlm_timeout_seconds,
                max_retries=updated.max_retries)

    return {"provider": provider, "config": _asdict(updated)}


# ───────────────────────── LLM Providers (Multi-source Priority) ─────────────────────────

@router.get("/system/llm-providers")
async def list_llm_providers(request: Request, _admin: AdminUser):
    """列出所有 LLM provider（含 priority、enabled）。"""
    redis = getattr(request.app.state, "redis", None)
    entries = await get_provider_entries(redis)
    return {"providers": [_asdict(e) for e in entries]}


@router.put("/system/llm-providers/reorder")
async def reorder_llm_providers(request: Request, _admin: AdminUser):
    """更新 LLM provider 优先级排序。"""
    redis = getattr(request.app.state, "redis", None)
    if not redis:
        return JSONResponse(status_code=503, content={
            "error_code": "REDIS_UNAVAILABLE",
            "message": "Redis is not available",
        })
    body = await request.json()
    ordered_names = body.get("ordered_names", [])
    if not ordered_names or not isinstance(ordered_names, list):
        return JSONResponse(status_code=400, content={
            "error_code": "INVALID_INPUT",
            "message": "ordered_names must be a non-empty array of provider names",
        })
    entries = await reorder_providers(redis, ordered_names)
    logger.info("llm_providers_reordered", names=ordered_names)
    return {"providers": [_asdict(e) for e in entries]}


@router.put("/system/llm-providers/{name}/toggle")
async def toggle_llm_provider(request: Request, name: str, _admin: AdminUser):
    """启用/禁用指定 LLM provider。"""
    redis = getattr(request.app.state, "redis", None)
    if not redis:
        return JSONResponse(status_code=503, content={
            "error_code": "REDIS_UNAVAILABLE",
            "message": "Redis is not available",
        })
    body = await request.json()
    enabled = body.get("enabled", True)
    entry = await toggle_provider(redis, name, enabled)
    if not entry:
        return JSONResponse(status_code=404, content={
            "error_code": "PROVIDER_NOT_FOUND",
            "message": f"Provider '{name}' not found",
        })
    logger.info("llm_provider_toggled", name=name, enabled=enabled)
    return {"provider": _asdict(entry)}


@router.put("/system/llm-providers/{name}")
async def update_llm_provider(request: Request, name: str, _admin: AdminUser):
    """更新指定 LLM provider 的超时/重试参数。"""
    redis = getattr(request.app.state, "redis", None)
    if not redis:
        return JSONResponse(status_code=503, content={
            "error_code": "REDIS_UNAVAILABLE",
            "message": "Redis is not available",
        })
    body = await request.json()
    allowed_fields = {"timeout_seconds", "vlm_timeout_seconds", "max_retries", "qpm_limit", "tpm_limit"}
    updates = {k: v for k, v in body.items() if k in allowed_fields}
    if not updates:
        return JSONResponse(status_code=400, content={
            "error_code": "NO_UPDATES",
            "message": f"No valid fields to update. Allowed: {allowed_fields}",
        })
    entry = await update_provider_entry(redis, name, updates)
    if not entry:
        return JSONResponse(status_code=404, content={
            "error_code": "PROVIDER_NOT_FOUND",
            "message": f"Provider '{name}' not found",
        })
    logger.info("llm_provider_updated", name=name, updates=updates)
    return {"provider": _asdict(entry)}


# ───────────────────────── Helpers ─────────────────────────

def _job_to_dict(job: PDFJob, detail: bool = False) -> dict:
    d = {
        "job_id": str(job.job_id),
        "source_file": job.source_file,
        "file_hash": job.file_hash,
        "merchant_id": job.merchant_id,
        "status": job.status,
        "user_status": job.user_status,
        "action_hint": job.action_hint,
        "route": job.route,
        "total_pages": job.total_pages,
        "total_skus": job.total_skus,
        "total_images": job.total_images,
        "blank_pages": job.blank_pages or [],
        "ai_pages": job.ai_pages or [],
        "human_pages": job.human_pages or [],
        "review_pages": job.review_pages or [],
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "eval_completed_at": job.eval_completed_at.isoformat() if job.eval_completed_at else None,
        "process_completed_at": job.process_completed_at.isoformat() if job.process_completed_at else None,
    }
    if detail:
        d.update({
            "file_hash": job.file_hash,
            "category": job.category,
            "worker_id": job.worker_id,
            "blank_pages": job.blank_pages,
            "ai_pages": job.ai_pages,
            "human_pages": job.human_pages,
            "failed_pages": job.failed_pages,
            "completion_source": job.completion_source,
            "error_message": job.error_message,
            "processing_trace": job.processing_trace,
            "token_consumption": job.token_consumption,
            "checkpoint_page": job.checkpoint_page,
        })
    return d


def _page_to_dict(p: Page) -> dict:
    return {
        "id": p.id,
        "job_id": str(p.job_id),
        "page_number": p.page_number,
        "status": p.status,
        "page_type": p.page_type,
        "layout_type": p.layout_type,
        "page_confidence": p.page_confidence,
        "needs_review": p.needs_review,
        "sku_count": p.sku_count,
        "extraction_method": p.extraction_method,
        "llm_model_used": p.llm_model_used,
        "parse_time_ms": p.parse_time_ms,
        "llm_time_ms": p.llm_time_ms,
        "retry_count": p.retry_count,
        "import_confirmation": p.import_confirmation,
    }
