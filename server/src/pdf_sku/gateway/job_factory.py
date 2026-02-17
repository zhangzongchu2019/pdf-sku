"""Job 创建工厂。对齐: Gateway 详设 §4.1 Step 1-8"""
from __future__ import annotations
import hashlib
import shutil
import uuid
from pathlib import Path
from dataclasses import asdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.enums import (
    JobInternalStatus, JobUserStatus, PageStatus, compute_user_status, ACTION_HINT_MAP,
)
from pdf_sku.common.exceptions import (
    FileSizeExceededError, PageCountExceededError, SecurityJavascriptError,
    SecurityEncryptedError, FileHashDuplicateError, JobNotFoundError,
)
from pdf_sku.common.models import PDFJob, Page, StateTransition
from pdf_sku.gateway.file_validator import FileValidator
from pdf_sku.gateway.pdf_security import PDFSecurityChecker
from pdf_sku.gateway.prescanner import Prescanner, PrescanRuleConfig
from pdf_sku.gateway.event_bus import event_bus
from pdf_sku.settings import settings
import structlog

logger = structlog.get_logger()

JOB_DATA_DIR = Path(os.environ.get("JOB_DATA_DIR", "/data/jobs")) if (os := __import__("os")) else Path("/data/jobs")


class JobFactory:
    def __init__(
        self,
        validator: FileValidator,
        security_checker: PDFSecurityChecker,
        prescanner: Prescanner,
    ) -> None:
        self._validator = validator
        self._security = security_checker
        self._prescanner = prescanner

    async def create_job(
        self,
        db: AsyncSession,
        redis,
        upload_file_path: Path,
        filename: str,
        merchant_id: str,
        category: str | None = None,
        uploaded_by: str = "",
    ) -> PDFJob:
        """
        创建 Job 主流程 (对齐 Gateway 详设 §4.1 Step 1-8):
        1. 文件校验 → 2. 安全检查 → 3. 冻结配置 → 4. 规则预筛
        5. 组装 Job → 6. 移动文件 → 7. 落库 → 8. 发事件
        """
        # === Step 1: 文件校验 ===
        validation = await self._validator.validate(upload_file_path)
        if not validation.valid:
            for err in validation.errors:
                if err.code == "PAGE_COUNT_EXCEEDED":
                    raise PageCountExceededError(err.message)
                raise FileSizeExceededError(err.message)

        # === Step 2: 安全检查 (进程池隔离) ===
        security = await self._security.check(str(upload_file_path))
        if not security.safe:
            for issue in security.security_issues:
                if "javascript" in issue:
                    raise SecurityJavascriptError("PDF contains JavaScript")
                if "encrypted" in issue:
                    raise SecurityEncryptedError("PDF is encrypted")
                raise FileSizeExceededError(f"Security check failed: {issue}")

        # === Step 3: 计算文件 hash + 去重检查 ===
        file_hash = await self._compute_file_hash(upload_file_path)
        existing = await db.execute(
            select(PDFJob).where(
                PDFJob.file_hash == file_hash,
                PDFJob.merchant_id == merchant_id,
                PDFJob.status.notin_(["CANCELLED", "REJECTED"]),
            ).limit(1)
        )
        if existing.scalar_one_or_none():
            raise FileHashDuplicateError(
                f"Duplicate file detected for merchant {merchant_id}")

        # === Step 4: 冻结配置版本 ===
        config_version = "default:v1.0"  # 初始默认, 运行时从 ConfigProvider 覆盖

        # === Step 5: 规则预筛 ===
        prescan = await self._prescanner.scan(str(upload_file_path))

        # === Step 6: 组装 Job ===
        job_id = uuid.uuid4()
        initial_status = JobInternalStatus.UPLOADED
        if prescan.all_blank:
            initial_status = JobInternalStatus.DEGRADED_HUMAN
            logger.warning("all_blank_pdf", job_id=str(job_id))

        user_status = compute_user_status(initial_status)
        action_hint = ACTION_HINT_MAP.get(user_status, "")

        job = PDFJob(
            job_id=job_id,
            source_file=filename,
            file_hash=file_hash,
            merchant_id=merchant_id,
            category=category,
            uploaded_by=uploaded_by,
            status=initial_status.value,
            user_status=user_status.value,
            action_hint=action_hint,
            frozen_config_version=config_version,
            worker_id=settings.worker_id,
            total_pages=validation.page_count or 0,
            blank_pages=prescan.blank_pages,
            processing_trace={
                "prescan": prescan.raw_metrics,
                "prescan_penalties": [
                    {"rule": p.rule, "actual": p.actual_value,
                     "threshold": p.threshold, "weight": p.weight}
                    for p in prescan.penalties
                ],
                "security_issues": security.security_issues,
                "file_size_mb": validation.file_size_mb,
            },
        )

        # === Step 7: 移动文件到 Job 目录 ===
        job_dir = JOB_DATA_DIR / str(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        dest_path = job_dir / "source.pdf"
        try:
            shutil.move(str(upload_file_path), str(dest_path))
        except Exception as e:
            logger.error("file_move_failed", job_id=str(job_id), error=str(e))
            raise

        # === Step 8: 落库 (失败则回滚文件) ===
        try:
            db.add(job)
            # 创建 Page 记录
            for page_no in range(1, job.total_pages + 1):
                page_status = PageStatus.BLANK if page_no in prescan.blank_pages else PageStatus.PENDING
                db.add(Page(
                    job_id=job_id,
                    page_number=page_no,
                    status=page_status.value,
                ))
            # 状态转换记录
            db.add(StateTransition(
                entity_type="job", entity_id=str(job_id),
                from_status=None, to_status=initial_status.value,
                trigger="upload",
            ))
            await db.flush()

            # Redis: Job → Worker 路由映射
            await redis.set(f"job_worker:{job_id}", settings.worker_id, ex=86400 * 7)

            logger.info("job_created",
                        job_id=str(job_id), status=initial_status.value,
                        pages=job.total_pages, blank=len(prescan.blank_pages),
                        file_hash=file_hash[:16], merchant_id=merchant_id)

        except Exception as e:
            # 回滚文件
            if dest_path.exists():
                shutil.move(str(dest_path), str(upload_file_path))
            raise

        # === Step 9: 发事件 ===
        await event_bus.publish("JobCreated", {
            "job_id": str(job_id),
            "file_hash": file_hash,
            "total_pages": job.total_pages,
            "status": initial_status.value,
            "prescan": prescan.raw_metrics,
            "config_version": config_version,
        })

        return job

    @staticmethod
    async def _compute_file_hash(file_path: Path) -> str:
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
