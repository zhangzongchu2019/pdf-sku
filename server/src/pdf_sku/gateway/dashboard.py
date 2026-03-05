"""
Dashboard 增强 — 实时指标 + 系统健康。
对齐: 前端 DashboardMetrics 类型。
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta

import uuid as uuid_mod
from sqlalchemy import select, func, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import (
    PDFJob, Page, HumanTask, CalibrationRecord, ImportDedup,
)
from pdf_sku.common.enums import JobInternalStatus, PageStatus
import structlog

logger = structlog.get_logger()


def _build_ownership_filter(owner_id: uuid_mod.UUID | None, legacy_uploaded_by: str | None):
    """Build SQLAlchemy filter for job ownership. Returns None when no filter needed (admin)."""
    if owner_id is None:
        return None
    return or_(
        PDFJob.owner_id == owner_id,
        and_(PDFJob.owner_id.is_(None), PDFJob.uploaded_by == legacy_uploaded_by),
    )


class DashboardService:

    async def get_overview(
        self,
        db: AsyncSession,
        owner_id: uuid_mod.UUID | None = None,
        legacy_uploaded_by: str | None = None,
    ) -> dict:
        ownership = _build_ownership_filter(owner_id, legacy_uploaded_by)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "job_stats": await self._job_stats(db, ownership),
            "page_stats": await self._page_stats(db, ownership),
            "task_stats": await self._task_stats(db),
            "import_stats": await self._import_stats(db),
            "calibration_stats": await self._calibration_stats(db),
        }

    async def _job_stats(self, db: AsyncSession, ownership_filter=None) -> dict:
        q = select(PDFJob.status, func.count().label("cnt")).group_by(PDFJob.status)
        if ownership_filter is not None:
            q = q.where(ownership_filter)
        result = await db.execute(q)
        by_status = {r.status or "unknown": r.cnt for r in result.all()}
        total = sum(by_status.values())
        active = sum(v for k, v in by_status.items()
                     if k in ("EVALUATING", "PROCESSING", "PARTIAL_FAILED"))
        completed = by_status.get(JobInternalStatus.FULL_IMPORTED.value, 0)
        return {
            "total": total,
            "active": active,
            "completed": completed,
            "by_status": by_status,
        }

    async def _page_stats(self, db: AsyncSession, ownership_filter=None) -> dict:
        q = select(Page.status, func.count().label("cnt")).group_by(Page.status)
        if ownership_filter is not None:
            q = q.join(PDFJob, Page.job_id == PDFJob.job_id).where(ownership_filter)
        result = await db.execute(q)
        dist = {r.status or "unknown": r.cnt for r in result.all()}
        total = sum(dist.values())
        completed = sum(v for k, v in dist.items()
                        if k in (PageStatus.AI_COMPLETED.value,
                                 PageStatus.IMPORTED_CONFIRMED.value,
                                 PageStatus.IMPORTED_ASSUMED.value))
        return {
            "total": total,
            "completed": completed,
            "completion_rate": round(completed / max(1, total), 4),
        }

    async def _task_stats(self, db: AsyncSession) -> dict:
        result = await db.execute(
            select(HumanTask.status, func.count().label("cnt"))
            .group_by(HumanTask.status)
        )
        dist = {r.status or "unknown": r.cnt for r in result.all()}
        queue_depth = sum(v for k, v in dist.items()
                          if k in ("CREATED", "ESCALATED"))

        now = datetime.now(timezone.utc)
        sla_cutoff = now - timedelta(hours=4)
        total_recent = (await db.execute(
            select(func.count()).select_from(HumanTask).where(
                HumanTask.created_at >= sla_cutoff)
        )).scalar() or 0
        overdue = (await db.execute(
            select(func.count()).select_from(HumanTask).where(
                HumanTask.created_at >= sla_cutoff,
                HumanTask.status.in_(["CREATED", "ESCALATED"]),
                HumanTask.created_at < now - timedelta(hours=1),
            )
        )).scalar() or 0
        return {
            "queue_depth": queue_depth,
            "sla_health": round(1.0 - overdue / max(1, total_recent), 4),
        }

    async def _import_stats(self, db: AsyncSession) -> dict:
        result = await db.execute(
            select(ImportDedup.import_status, func.count().label("cnt"))
            .group_by(ImportDedup.import_status)
        )
        dist = {r.import_status: r.cnt for r in result.all()}
        total = sum(dist.values())
        success = dist.get("CONFIRMED", 0) + dist.get("ASSUMED", 0)
        return {
            "success_rate": round(success / max(1, total), 4),
        }

    async def _calibration_stats(self, db: AsyncSession) -> dict:
        result = await db.execute(
            select(CalibrationRecord.status, func.count().label("cnt"))
            .group_by(CalibrationRecord.status)
        )
        dist = {r.status: r.cnt for r in result.all()}
        return {
            "pending_approvals": dist.get("PENDING", 0),
        }
