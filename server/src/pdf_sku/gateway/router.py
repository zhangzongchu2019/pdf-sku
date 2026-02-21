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
from pdf_sku.auth.dependencies import CurrentUser, UploaderUser, AnyUser
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
    await db.commit()

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

    blank_pages = set(job.blank_pages or [])
    await db.execute(
        update(Page)
        .where(Page.job_id == job_id)
        .values(status="PENDING", needs_review=False, sku_count=0)
    )
    if blank_pages:
        await db.execute(
            update(Page)
            .where(Page.job_id == job_id, Page.page_number.in_(list(blank_pages)))
            .values(status="BLANK")
        )

    await db.commit()

    eval_data = {
        "job_id": str(job_id),
        "route": "AI_ONLY",
        "degrade_reason": None,
        "prescan": {"blank_pages": sorted(blank_pages)},
    }
    await event_bus.publish("EvaluationCompleted", eval_data)

    return {
        "job_id": str(job_id),
        "queued": True,
        "route": "AI_ONLY",
        "deleted_human_tasks": deleted_tasks,
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
    img = result.scalar_one_or_none()
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
        } for s in skus],
        "pagination": {"page": page, "page_size": page_size,
                        "total_count": count, "total_pages": (count + page_size - 1) // page_size},
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
