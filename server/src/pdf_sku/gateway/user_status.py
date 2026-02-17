"""
user_status 实时聚合服务。对齐: Data Dictionary §3.3 user_status 状态机

两种更新时机:
1. status 变更时同步计算 (update_user_status)
2. 查询时实时聚合 (compute_from_pages) — 兜底一致性
"""
from __future__ import annotations
from sqlalchemy import select, func, update, case
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import PDFJob, Page
from pdf_sku.common.enums import (
    JobInternalStatus, JobUserStatus, PageStatus,
    compute_user_status, ACTION_HINT_MAP,
)
import structlog

logger = structlog.get_logger()


async def update_job_status(
    db: AsyncSession,
    job_id: str,
    new_internal_status: str,
    trigger: str = "",
    error_message: str | None = None,
) -> PDFJob:
    """
    更新 Job 内部状态 + 同步计算 user_status/action_hint。
    写入 state_transitions 审计记录。
    """
    from pdf_sku.common.models import StateTransition

    result = await db.execute(select(PDFJob).where(PDFJob.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        from pdf_sku.common.exceptions import JobNotFoundError
        raise JobNotFoundError(f"Job {job_id} not found")

    old_status = job.status
    job.status = new_internal_status
    job.user_status = compute_user_status(new_internal_status).value
    job.action_hint = ACTION_HINT_MAP.get(job.user_status, "")
    if error_message:
        job.error_message = error_message

    # 审计记录
    db.add(StateTransition(
        entity_type="job",
        entity_id=str(job_id),
        from_status=old_status,
        to_status=new_internal_status,
        trigger=trigger,
    ))

    logger.info("job_status_updated",
                job_id=str(job_id),
                old=old_status, new=new_internal_status,
                user_status=job.user_status, trigger=trigger)
    return job


async def refresh_job_page_stats(db: AsyncSession, job_id: str) -> PDFJob:
    """
    从 pages 表聚合统计，更新 Job 的页面计数数组 + total_skus。
    用于 Pipeline 完成后的一致性刷新。
    """
    result = await db.execute(select(PDFJob).where(PDFJob.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        from pdf_sku.common.exceptions import JobNotFoundError
        raise JobNotFoundError(f"Job {job_id} not found")

    # 按状态分组聚合页号
    page_result = await db.execute(
        select(Page.status, func.array_agg(Page.page_number))
        .where(Page.job_id == job_id, Page.attempt_no == 1)
        .group_by(Page.status)
    )

    status_pages: dict[str, list[int]] = {}
    for row in page_result:
        status_pages[row[0]] = sorted(row[1])

    job.blank_pages = status_pages.get(PageStatus.BLANK.value, [])
    job.ai_pages = sorted(
        status_pages.get(PageStatus.AI_COMPLETED.value, []) +
        status_pages.get(PageStatus.AI_PROCESSING.value, [])
    )
    job.human_pages = sorted(
        status_pages.get(PageStatus.HUMAN_QUEUED.value, []) +
        status_pages.get(PageStatus.HUMAN_PROCESSING.value, []) +
        status_pages.get(PageStatus.HUMAN_COMPLETED.value, [])
    )
    job.skipped_pages = status_pages.get(PageStatus.SKIPPED.value, [])
    job.failed_pages = sorted(
        status_pages.get(PageStatus.AI_FAILED.value, []) +
        status_pages.get(PageStatus.HUMAN_FAILED.value, [])
    )

    # SKU 总数
    from pdf_sku.common.models import SKU
    sku_count_result = await db.execute(
        select(func.count()).where(SKU.job_id == job_id, SKU.superseded == False)
    )
    job.total_skus = sku_count_result.scalar() or 0

    return job
