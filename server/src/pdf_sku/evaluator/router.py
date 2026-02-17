"""
EvaluatorService — 主入口。对齐: Evaluator 详设 §5.1

调用链:
1. Prescan Guard → all_blank 直接降级
2. Cache 查询 (Redis → DB)
3. 分布式锁内评估:
   a. 采样 (Sampler)
   b. 截图渲染 (PyMuPDF)
   c. LLM 评估 (LLMService)
   d. 聚合评分 (Scorer → C_doc)
   e. 方差检测 (VarianceDetector)
   f. 路由决策 (RouteDecider)
4. 持久化 + 缓存
5. 更新 Job 状态 (UPLOADED → EVALUATED)
"""
from __future__ import annotations
import asyncio
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import PDFJob, Evaluation as EvalModel
from pdf_sku.common.enums import JobInternalStatus
from pdf_sku.gateway.event_bus import event_bus
from pdf_sku.gateway.user_status import update_job_status
from pdf_sku.evaluator.sampler import Sampler
from pdf_sku.evaluator.scorer import Scorer, PageScore
from pdf_sku.evaluator.router_logic import RouteDecider
from pdf_sku.evaluator.variance_detector import VarianceDetector
from pdf_sku.evaluator.eval_cache import EvalCache
from pdf_sku.config.service import ConfigProvider
from pdf_sku.common.exceptions import EvalFailedError
import structlog

logger = structlog.get_logger()

# 进程池 (PDF 渲染)
_render_pool: ProcessPoolExecutor | None = None


def _render_pages_batch(file_path: str, pages: list[int], dpi: int = 150) -> list[bytes]:
    """在子进程中渲染 PDF 页面为 PNG 截图。"""
    import fitz
    screenshots = []
    doc = fitz.open(file_path)
    try:
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        for page_no in pages:
            if 1 <= page_no <= doc.page_count:
                page = doc[page_no - 1]
                pix = page.get_pixmap(matrix=mat)
                screenshots.append(pix.tobytes("png"))
            else:
                screenshots.append(b"")
    finally:
        doc.close()
    return screenshots


class EvaluatorService:
    """文档质量评估 + 路由决策的完整编排器。"""

    def __init__(
        self,
        llm_service,
        cache: EvalCache,
        config_provider: ConfigProvider,
        process_pool: ProcessPoolExecutor | None = None,
    ) -> None:
        self._llm = llm_service
        self._cache = cache
        self._config = config_provider
        self._sampler = Sampler()
        self._scorer = Scorer()
        self._router = RouteDecider()
        self._variance = VarianceDetector()
        self._pool = process_pool

    async def evaluate(
        self,
        db: AsyncSession,
        job: PDFJob,
        prescan_data: dict,
    ) -> dict:
        """
        评估入口。

        Args:
            db: 数据库会话
            job: PDFJob ORM 对象
            prescan_data: 预筛结果 (raw_metrics)
        Returns:
            评估结果 dict (route, doc_confidence, ...)
        """
        start_time = time.monotonic()

        # 获取冻结配置
        profile = await self._config.get_frozen_config(
            db, job.frozen_config_version or "default:v1.0")
        thresholds = profile.get("thresholds", {"A": 0.85, "B": 0.45})
        weights = profile.get("confidence_weights")

        # [P0-5] Prescan Guard: all_blank 直接降级
        if prescan_data.get("blank_rate", 0) == 1.0 or prescan_data.get("all_blank"):
            return await self._create_degraded(
                db, job, prescan_data, profile,
                route="HUMAN_ALL", reason="prescan_reject")

        # 缓存查询
        cache_key = f"{job.file_hash}:{job.frozen_config_version or 'default:v1.0'}"
        cached = await self._cache.get(cache_key)
        if cached:
            logger.info("eval_cache_hit", job_id=str(job.job_id), key=cache_key)
            # 更新 Job 状态
            await self._update_job_after_eval(db, job, cached)
            return cached

        # 分布式锁内评估
        async with self._cache.lock(cache_key) as lock_ok:
            # Double-check cache
            cached = await self._cache.get(cache_key)
            if cached:
                await self._update_job_after_eval(db, job, cached)
                return cached

            try:
                result = await self._evaluate_inner(
                    db, job, prescan_data, profile, thresholds, weights, cache_key)
            except Exception as e:
                # [P0-3] 评估失败降级
                logger.error("eval_failed_degrade",
                             job_id=str(job.job_id), error=str(e))
                result = await self._create_degraded(
                    db, job, prescan_data, profile,
                    route="HUMAN_ALL",
                    reason=f"eval_failed:{type(e).__name__}")

        elapsed = time.monotonic() - start_time
        logger.info("evaluation_complete",
                     job_id=str(job.job_id),
                     route=result.get("route"),
                     c_doc=result.get("doc_confidence"),
                     elapsed_ms=int(elapsed * 1000))
        return result

    async def _evaluate_inner(
        self,
        db: AsyncSession,
        job: PDFJob,
        prescan_data: dict,
        profile: dict,
        thresholds: dict,
        weights: dict | None,
        cache_key: str,
    ) -> dict:
        """实际评估逻辑 (锁内执行)。"""
        # 1. 采样
        sample_pages = self._sampler.select_pages(
            total=job.total_pages,
            blank_pages=job.blank_pages or [],
            threshold=40,
        )
        if not sample_pages:
            return await self._create_degraded(
                db, job, prescan_data, profile,
                route="HUMAN_ALL", reason="no_pages_to_sample")

        # 2. 截图渲染
        file_path = self._resolve_file_path(job)
        loop = asyncio.get_event_loop()
        if self._pool:
            screenshots = await loop.run_in_executor(
                self._pool, _render_pages_batch, str(file_path), sample_pages)
        else:
            screenshots = _render_pages_batch(str(file_path), sample_pages)

        # 过滤空截图
        valid_pairs = [(p, s) for p, s in zip(sample_pages, screenshots) if s]
        if not valid_pairs:
            return await self._create_degraded(
                db, job, prescan_data, profile,
                route="HUMAN_ALL", reason="screenshot_render_failed")

        valid_pages, valid_screenshots = zip(*valid_pairs)

        # 3. LLM 评估
        page_scores = await self._llm.evaluate_document(
            screenshots=list(valid_screenshots),
            category=job.category,
            sample_pages=list(valid_pages),
        )

        # 4. 聚合评分
        dimension_scores = self._scorer.aggregate(page_scores)
        prescan_penalty = prescan_data.get("total_penalty", 0.0)
        if isinstance(prescan_penalty, list):
            prescan_penalty = sum(p.get("weight", 0) for p in prescan_penalty) if prescan_penalty else 0.0
        c_doc = self._scorer.compute_c_doc(dimension_scores, weights, prescan_penalty)

        # 5. 方差检测
        overall_scores = [ps.overall for ps in page_scores]
        variance_threshold = profile.get("prescan_rules", {}).get("score_variance_threshold", 0.08)
        variance, variance_forced = self._variance.check(
            overall_scores, variance_threshold=variance_threshold)

        # 6. 路由决策
        route, route_reason = self._router.decide(c_doc, thresholds, variance_forced)

        # 7. 持久化
        eval_data = {
            "file_hash": job.file_hash,
            "config_version": job.frozen_config_version or "default:v1.0",
            "doc_confidence": c_doc,
            "route": route,
            "route_reason": route_reason,
            "degrade_reason": None,
            "dimension_scores": dimension_scores,
            "weights_snapshot": weights or {},
            "thresholds_used": thresholds,
            "prescan": prescan_data,
            "sampling": {
                "pages": list(valid_pages),
                "sample_ratio": len(valid_pages) / max(job.total_pages, 1),
                "variance": variance,
                "variance_forced": variance_forced,
            },
            "page_evaluations": {
                str(ps.page_no): ps.overall for ps in page_scores
            },
            "model_used": self._llm.current_model_name,
        }

        # 写 DB
        db.add(EvalModel(
            job_id=job.job_id,
            file_hash=eval_data["file_hash"],
            config_version=eval_data["config_version"],
            doc_confidence=c_doc,
            route=route,
            route_reason=route_reason,
            dimension_scores=dimension_scores,
            weights_snapshot=weights or {},
            thresholds_used=thresholds,
            prescan=prescan_data,
            sampling=eval_data["sampling"],
            page_evaluations=eval_data["page_evaluations"],
            model_used=eval_data["model_used"],
        ))

        # 写缓存
        await self._cache.put(cache_key, eval_data)

        # 更新 Job
        await self._update_job_after_eval(db, job, eval_data)

        return eval_data

    async def _create_degraded(
        self,
        db: AsyncSession,
        job: PDFJob,
        prescan_data: dict,
        profile: dict,
        route: str,
        reason: str,
    ) -> dict:
        """创建降级评估结果。"""
        eval_data = {
            "file_hash": job.file_hash,
            "config_version": job.frozen_config_version or "default:v1.0",
            "doc_confidence": 0.0,
            "route": route,
            "route_reason": None,
            "degrade_reason": reason,
            "dimension_scores": {},
            "weights_snapshot": profile.get("confidence_weights", {}),
            "thresholds_used": profile.get("thresholds", {}),
            "prescan": prescan_data,
            "sampling": {"pages": [], "sample_ratio": 0.0, "variance": 0.0},
            "page_evaluations": {},
            "model_used": None,
        }

        db.add(EvalModel(
            job_id=job.job_id,
            file_hash=eval_data["file_hash"],
            config_version=eval_data["config_version"],
            doc_confidence=0.0,
            route=route,
            degrade_reason=reason,
            dimension_scores={},
            weights_snapshot=eval_data["weights_snapshot"],
            thresholds_used=eval_data["thresholds_used"],
            prescan=prescan_data,
            sampling=eval_data["sampling"],
            page_evaluations={},
            model_used="",
        ))

        await self._update_job_after_eval(db, job, eval_data)
        logger.warning("eval_degraded",
                        job_id=str(job.job_id), route=route, reason=reason)
        return eval_data

    async def _update_job_after_eval(
        self, db: AsyncSession, job: PDFJob, eval_data: dict
    ) -> None:
        """评估完成 → 更新 Job 状态。"""
        route = eval_data.get("route", "HUMAN_ALL")
        degrade = eval_data.get("degrade_reason")

        if degrade:
            new_status = JobInternalStatus.DEGRADED_HUMAN.value
        else:
            new_status = JobInternalStatus.EVALUATED.value

        job.route = route
        job.degrade_reason = degrade
        await update_job_status(db, str(job.job_id), new_status,
                                trigger="evaluation_complete")

        # 发事件
        await event_bus.publish("EvaluationCompleted", {
            "job_id": str(job.job_id),
            "route": route,
            "doc_confidence": eval_data.get("doc_confidence", 0.0),
            "degrade_reason": degrade,
        })

    @staticmethod
    def _resolve_file_path(job: PDFJob) -> Path:
        """获取 Job 的 PDF 文件路径。"""
        import os
        job_dir = Path(os.environ.get("JOB_DATA_DIR", "/data/jobs")) / str(job.job_id)
        return job_dir / "source.pdf"
