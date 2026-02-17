"""
对账轮询。对齐: Output 详设 §4.3

- IMPORTED_ASSUMED → check_status → IMPORTED_CONFIRMED
- IMPORT_FAILED 滞留 > 24h → SKIPPED
- Job 终态判定 (并发保护)
- [P0-2] I5 降级: 24h 自动确认
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from collections import Counter

from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import PDFJob, Page
from pdf_sku.common.enums import JobInternalStatus, PageStatus
from pdf_sku.output.import_adapter import ImportAdapter
from pdf_sku.gateway.user_status import update_job_status
import structlog

logger = structlog.get_logger()

ASSUMED_AUTO_CONFIRM_SEC = 86400  # 24h
FAILED_STALE_THRESHOLD = 86400   # 24h
TERMINAL_PAGE_STATUSES = {
    PageStatus.AI_COMPLETED.value,
    PageStatus.IMPORTED_CONFIRMED.value,
    PageStatus.IMPORTED_ASSUMED.value,
    PageStatus.BLANK.value,
}


class ReconciliationPoller:
    def __init__(self, adapter: ImportAdapter | None = None):
        self._adapter = adapter or ImportAdapter()

    async def reconcile(self, db: AsyncSession) -> dict:
        """
        执行一轮对账:
        1. ASSUMED → 确认
        2. FAILED 滞留 → SKIPPED
        3. Job 终态判定
        """
        stats = {"confirmed": 0, "auto_confirmed": 0, "stale_skipped": 0, "finalized": 0}

        # 1. IMPORTED_ASSUMED → 确认
        result = await db.execute(
            select(Page).where(Page.import_confirmation == "imported_assumed")
        )
        assumed_pages = result.scalars().all()
        now = datetime.now(timezone.utc)

        for page in assumed_pages:
            confirmed = await self._adapter.check_status(
                str(page.job_id), page.page_number)
            if confirmed is True:
                await db.execute(
                    update(Page).where(Page.id == page.id)
                    .values(import_confirmation="imported_confirmed")
                )
                stats["confirmed"] += 1
            elif confirmed is None:
                # I5 降级: 超 24h 自动确认
                age = (now - (page.claimed_at or now)).total_seconds()
                if age > ASSUMED_AUTO_CONFIRM_SEC:
                    await db.execute(
                        update(Page).where(Page.id == page.id)
                        .values(import_confirmation="imported_confirmed")
                    )
                    stats["auto_confirmed"] += 1

        # 2. IMPORT_FAILED 滞留 → 标记
        cutoff = now - timedelta(seconds=FAILED_STALE_THRESHOLD)
        result = await db.execute(
            select(Page).where(
                Page.status == PageStatus.AI_FAILED.value,
                Page.claimed_at < cutoff,
            )
        )
        stale = result.scalars().all()
        for page in stale:
            await db.execute(
                update(Page).where(Page.id == page.id)
                .values(status=PageStatus.BLANK.value)  # 标记为跳过
            )
            stats["stale_skipped"] += 1

        # 3. Job 终态判定
        stats["finalized"] = await self._check_job_completion(db)

        if any(v > 0 for v in stats.values()):
            logger.info("reconciliation_complete", **stats)
        return stats

    async def _check_job_completion(self, db: AsyncSession) -> int:
        """检查活跃 Job 是否可以标记为 FULL_IMPORTED。"""
        result = await db.execute(
            select(PDFJob).where(
                PDFJob.internal_status.in_([
                    JobInternalStatus.PROCESSING.value,
                    JobInternalStatus.PARTIAL_FAILED.value,
                ])
            )
        )
        active_jobs = result.scalars().all()
        finalized = 0

        for job in active_jobs:
            page_result = await db.execute(
                select(
                    Page.status,
                    func.count().label("cnt"),
                ).where(Page.job_id == job.job_id)
                .group_by(Page.status)
            )
            status_counts = {r.status: r.cnt for r in page_result.all()}

            total = sum(status_counts.values())
            blank = status_counts.get(PageStatus.BLANK.value, 0)
            completed = status_counts.get(PageStatus.AI_COMPLETED.value, 0)
            imported = (status_counts.get(PageStatus.IMPORTED_CONFIRMED.value, 0) +
                       status_counts.get(PageStatus.IMPORTED_ASSUMED.value, 0))
            failed = status_counts.get(PageStatus.AI_FAILED.value, 0)
            human = (status_counts.get(PageStatus.HUMAN_QUEUED.value, 0) +
                     status_counts.get(PageStatus.HUMAN_PROCESSING.value, 0))

            total_valid = total - blank
            done = completed + imported

            if human > 0:
                continue  # 等人工
            elif failed > 0 and done == 0:
                continue  # 全失败, 保持 PARTIAL_FAILED
            elif done >= total_valid and total_valid > 0:
                # 条件 UPDATE (并发保护)
                r = await db.execute(
                    update(PDFJob).where(
                        PDFJob.job_id == job.job_id,
                        PDFJob.internal_status != JobInternalStatus.FULL_IMPORTED.value,
                    ).values(
                        internal_status=JobInternalStatus.FULL_IMPORTED.value,
                        completion_snapshot=self._build_snapshot(status_counts, job),
                    )
                )
                if r.rowcount > 0:
                    finalized += 1
                    logger.info("job_finalized",
                                job_id=str(job.job_id), status="FULL_IMPORTED")

        return finalized

    @staticmethod
    def _build_snapshot(status_counts: dict, job: PDFJob) -> dict:
        """构建 completion_snapshot。"""
        return {
            "snapshot_at": datetime.now(timezone.utc).isoformat(),
            "total_pages": job.total_pages,
            "status_distribution": status_counts,
            "evidence": {
                "route": job.route,
                "file_hash": job.file_hash,
            },
        }
