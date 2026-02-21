import os
import sys
import asyncio
from pathlib import Path

from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from redis.asyncio import Redis

# usage: python scripts/reprocess_job_ai.py <job_id>
JOB_ID = sys.argv[1]

# Ensure project imports
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "src"))

from pdf_sku.settings import settings
from pdf_sku.common.models import (
    PDFJob,
    Page,
    HumanTask,
    Annotation,
    StateTransition,
    SKU,
    Image,
    SKUImageBinding,
)
from pdf_sku.llm_adapter.client.registry import register as register_client
from pdf_sku.llm_adapter.client.qwen import QwenClient
from pdf_sku.llm_adapter.client.gemini import GeminiClient
from pdf_sku.llm_adapter.service import LLMService
from pdf_sku.llm_adapter.prompt.engine import PromptEngine
from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
from pdf_sku.llm_adapter.resilience.circuit_breaker import CircuitBreaker
from pdf_sku.llm_adapter.resilience.budget_guard import BudgetGuard
from pdf_sku.llm_adapter.resilience.rate_limiter import RateLimiter
from pdf_sku.config.service import ConfigProvider
from pdf_sku.pipeline.page_processor import PageProcessor
from pdf_sku.pipeline.orchestrator import Orchestrator


async def main() -> None:
    os.environ.setdefault("JOB_DATA_DIR", str(ROOT / "data" / "jobs"))

    redis = Redis.from_url(settings.redis_url, decode_responses=True)

    if settings.gemini_api_key:
        register_client("gemini", GeminiClient(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout=settings.llm_timeout_seconds,
        ))
    if settings.qwen_api_key:
        register_client("qwen", QwenClient(
            api_key=settings.qwen_api_key,
            model=settings.qwen_model,
            timeout=settings.llm_timeout_seconds,
        ))

    llm_service = LLMService(
        prompt_engine=PromptEngine(),
        parser=ResponseParser(),
        circuit_breaker=CircuitBreaker(),
        budget_guard=BudgetGuard(redis),
        rate_limiter=RateLimiter(redis),
        default_client_name="gemini" if settings.gemini_api_key else "qwen",
    )

    engine = create_async_engine(settings.database_url, pool_size=5, max_overflow=10, echo=False)
    Session = async_sessionmaker(engine, expire_on_commit=False)

    orchestrator = Orchestrator(
        page_processor=PageProcessor(llm_service=llm_service, config_provider=ConfigProvider()),
        db_session_factory=Session,
    )

    async with Session() as db:
        job = (await db.execute(select(PDFJob).where(PDFJob.job_id == JOB_ID))).scalar_one_or_none()
        if not job:
            print("job_not_found")
            return

        # Clean human tasks for this job
        task_ids = (await db.execute(select(HumanTask.task_id).where(HumanTask.job_id == JOB_ID))).scalars().all()
        if task_ids:
            await db.execute(delete(StateTransition).where(
                StateTransition.entity_type == "task",
                StateTransition.entity_id.in_([str(tid) for tid in task_ids]),
            ))
            await db.execute(delete(Annotation).where(Annotation.task_id.in_(task_ids)))
        await db.execute(delete(HumanTask).where(HumanTask.job_id == JOB_ID))

        # Reset AI outputs, then re-run AI
        await db.execute(delete(SKUImageBinding).where(SKUImageBinding.job_id == JOB_ID))
        await db.execute(delete(Image).where(Image.job_id == JOB_ID))
        await db.execute(delete(SKU).where(SKU.job_id == JOB_ID))

        blank_pages = set(job.blank_pages or [])
        await db.execute(update(Page).where(Page.job_id == JOB_ID).values(status="PENDING", sku_count=0, needs_review=False))
        if blank_pages:
            await db.execute(update(Page).where(Page.job_id == JOB_ID, Page.page_number.in_(list(blank_pages))).values(status="BLANK"))

        job.route = "AI_ONLY"
        job.degrade_reason = None
        await db.commit()

        await orchestrator.process_job(db, job, {
            "route": "AI_ONLY",
            "prescan": {"blank_pages": sorted(blank_pages)},
        })
        await db.commit()

        latest = (await db.execute(select(PDFJob).where(PDFJob.job_id == JOB_ID))).scalar_one()
        page_rows = (await db.execute(
            select(Page.status, func.count())
            .where(Page.job_id == JOB_ID)
            .group_by(Page.status)
        )).all()

        print("job_status", latest.status, latest.user_status, latest.route)
        print("page_counts", {status: count for status, count in page_rows})

    await redis.aclose()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
