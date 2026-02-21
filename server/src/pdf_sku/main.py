"""
PDF-SKU Server 应用入口。

启动: uvicorn pdf_sku.main:create_app --factory --reload --port 8000
需要: PostgreSQL + Redis + MinIO (docker compose up)
"""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from concurrent.futures import ProcessPoolExecutor

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pdf_sku.settings import settings

logger = structlog.get_logger()


def _configure_logging() -> None:
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]
    if settings.app_env == "development":
        processors.append(structlog.dev.ConsoleRenderer())
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40}
            .get(settings.log_level, 20)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    _configure_logging()
    log = structlog.get_logger()
    log.info("startup_begin", env=settings.app_env, worker=settings.worker_id)

    # Track service readiness
    app.state.services_ready = {
        "database": False, "redis": False, "minio": False,
    }

    # ─── 1. Database ───
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    try:
        engine = create_async_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            echo=settings.sql_echo,
        )
        # Test connection
        async with engine.connect() as conn:
            await conn.execute(engine.dialect.do_ping(conn) if False else __import__("sqlalchemy").text("SELECT 1"))
        app.state.engine = engine
        app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
        app.state.services_ready["database"] = True
        log.info("database_connected")
    except Exception as e:
        log.error("database_connection_failed", error=str(e))
        app.state.engine = None
        app.state.session_factory = None

    # ─── 2. Redis ───
    try:
        from redis.asyncio import Redis
        redis = Redis.from_url(settings.redis_url, decode_responses=True)
        await redis.ping()
        app.state.redis = redis
        app.state.services_ready["redis"] = True
        log.info("redis_connected")
    except Exception as e:
        log.error("redis_connection_failed", error=str(e))
        app.state.redis = None

    # ─── 3. MinIO ───
    try:
        from pdf_sku.storage.minio_provider import MinioStorageProvider
        storage = MinioStorageProvider()
        await storage.ensure_bucket()
        app.state.storage = storage
        app.state.services_ready["minio"] = True
        log.info("minio_connected")
    except Exception as e:
        log.error("minio_connection_failed", error=str(e))
        app.state.storage = None

    process_pool = ProcessPoolExecutor(max_workers=2)
    bg_tasks: list[asyncio.Task] = []

    # ─── 4. Component assembly (only if DB + Redis ready) ───
    if app.state.services_ready["database"] and app.state.services_ready["redis"]:
        session_factory = app.state.session_factory
        redis = app.state.redis

        try:
            # Gateway
            import pdf_sku.gateway._deps as deps
            from pdf_sku.gateway.tus_store import TusStore
            from pdf_sku.gateway.tus_handler import TusHandler
            from pdf_sku.gateway.file_validator import FileValidator
            from pdf_sku.gateway.pdf_security import PDFSecurityChecker
            from pdf_sku.gateway.prescanner import Prescanner
            from pdf_sku.gateway.job_factory import JobFactory
            from pdf_sku.gateway.sse_manager import SSEManager
            from pdf_sku.gateway.orphan_scanner import OrphanScanner

            deps.tus_store = TusStore(redis)
            deps.tus_handler = TusHandler(deps.tus_store)
            deps.job_factory = JobFactory(
                validator=FileValidator(),
                security_checker=PDFSecurityChecker(process_pool),
                prescanner=Prescanner(),
            )
            deps.sse_manager = SSEManager()
            deps.orphan_scanner = OrphanScanner(session_factory, redis)
            log.info("gateway_initialized")

            # LLM Clients
            from pdf_sku.llm_adapter.client.registry import register as register_client
            if settings.gemini_api_key:
                from pdf_sku.llm_adapter.client.gemini import GeminiClient
                register_client("gemini", GeminiClient(
                    api_key=settings.gemini_api_key,
                    model=settings.gemini_model,
                    timeout=settings.llm_timeout_seconds,
                ))
                log.info("llm_registered", client="gemini")
            if settings.qwen_api_key:
                from pdf_sku.llm_adapter.client.qwen import QwenClient
                register_client("qwen", QwenClient(
                    api_key=settings.qwen_api_key,
                    model=settings.qwen_model,
                    timeout=settings.llm_timeout_seconds,
                ))
                log.info("llm_registered", client="qwen")

            # LLM Service
            from pdf_sku.llm_adapter.service import LLMService
            from pdf_sku.llm_adapter.prompt.engine import PromptEngine
            from pdf_sku.llm_adapter.parser.response_parser import ResponseParser
            from pdf_sku.llm_adapter.resilience.circuit_breaker import CircuitBreaker
            from pdf_sku.llm_adapter.resilience.budget_guard import BudgetGuard
            from pdf_sku.llm_adapter.resilience.rate_limiter import RateLimiter

            llm_service = LLMService(
                prompt_engine=PromptEngine(),
                parser=ResponseParser(),
                circuit_breaker=CircuitBreaker(),
                budget_guard=BudgetGuard(redis) if settings.gemini_api_key else None,
                rate_limiter=RateLimiter(redis) if settings.gemini_api_key else None,
                default_client_name="gemini" if settings.gemini_api_key else "qwen",
            )

            # Evaluator
            from pdf_sku.evaluator.eval_cache import EvalCache
            from pdf_sku.evaluator.router import EvaluatorService
            from pdf_sku.config.service import ConfigProvider

            evaluator_service = EvaluatorService(
                llm_service=llm_service,
                cache=EvalCache(redis, session_factory),
                config_provider=ConfigProvider(),
                process_pool=process_pool,
            )

            from pdf_sku.evaluator._handler import init_handler as init_eval_handler
            init_eval_handler(evaluator_service, session_factory)
            log.info("evaluator_initialized")

            # Pipeline
            from pdf_sku.pipeline.page_processor import PageProcessor
            from pdf_sku.pipeline.orchestrator import Orchestrator

            orchestrator = Orchestrator(
                page_processor=PageProcessor(
                    llm_service=llm_service,
                    process_pool=process_pool,
                    config_provider=ConfigProvider(),
                ),
                db_session_factory=session_factory,
            )

            from pdf_sku.pipeline._handler import init_handler as init_pipeline_handler
            init_pipeline_handler(orchestrator, session_factory)
            log.info("pipeline_initialized")

            # Output
            from pdf_sku.output.import_adapter import ImportAdapter
            from pdf_sku.output.backpressure import BackpressureMonitor
            from pdf_sku.output.importer import IncrementalImporter

            import_adapter = ImportAdapter(
                import_url=settings.downstream_import_url,
                check_url=settings.downstream_check_url,
            )
            importer = IncrementalImporter(
                adapter=import_adapter,
                backpressure=BackpressureMonitor(),
            )

            from pdf_sku.output._handler import init_output_handler
            init_output_handler(importer, session_factory)
            log.info("output_initialized")

            # Collaboration
            from pdf_sku.collaboration.annotation_service import TaskManager
            from pdf_sku.collaboration.sla_monitor import SLAScanner
            from pdf_sku.collaboration.lock_manager import LockManager
            from pdf_sku.collaboration.notification import Notifier

            task_manager = TaskManager()
            sla_scanner = SLAScanner(notifier=Notifier(), task_manager=task_manager)

            # Feedback + Scheduler
            from pdf_sku.feedback.calibration_engine import CalibrationEngine
            from pdf_sku.feedback.promotion_checker import AttrPromotionChecker
            from pdf_sku.feedback.scheduler import ScheduledTaskRunner
            from pdf_sku.output.reconciler import ReconciliationPoller
            from pdf_sku.feedback._handler import init_feedback_handler
            from pdf_sku.feedback.fewshot_sync import FewShotSyncer

            calibration_engine = CalibrationEngine(
                notifier=Notifier(
                    wecom_url=settings.wecom_webhook_url,
                    dingtalk_url=settings.dingtalk_webhook_url,
                )
            )
            scheduled_runner = ScheduledTaskRunner(
                calibration_engine=calibration_engine,
                promotion_checker=AttrPromotionChecker(),
                sla_scanner=sla_scanner,
                lock_manager=LockManager(),
                reconciler=ReconciliationPoller(adapter=import_adapter),
                db_session_factory=session_factory,
            )
            init_feedback_handler(FewShotSyncer(), session_factory)
            log.info("feedback_initialized")

            # Background tasks
            from pdf_sku.gateway.heartbeat import heartbeat_loop

            bg_tasks.append(asyncio.create_task(heartbeat_loop(redis, session_factory)))

            async def orphan_loop():
                while True:
                    try:
                        await deps.orphan_scanner.scan()
                    except Exception:
                        log.exception("orphan_scan_error")
                    await asyncio.sleep(60)

            bg_tasks.append(asyncio.create_task(orphan_loop()))
            await scheduled_runner.start()
            log.info("background_tasks_started", count=len(bg_tasks))

        except Exception as e:
            log.exception("component_assembly_failed", error=str(e))

    # ─── 5. Dependency injection ───
    from pdf_sku.common.dependencies import get_db, get_redis

    if app.state.session_factory:
        sf = app.state.session_factory

        async def _get_db():
            async with sf() as session:
                try:
                    yield session
                    await session.commit()
                except Exception:
                    await session.rollback()
                    raise

        app.dependency_overrides[get_db] = _get_db

    if app.state.redis:
        _redis = app.state.redis
        async def _get_redis():
            return _redis
        app.dependency_overrides[get_redis] = _get_redis

    all_ready = all(app.state.services_ready.values())
    log.info("startup_complete", all_services_ready=all_ready,
             services=app.state.services_ready)

    yield

    # ─── Shutdown ───
    log.info("shutdown_begin")
    for task in bg_tasks:
        task.cancel()
    await asyncio.gather(*bg_tasks, return_exceptions=True)
    process_pool.shutdown(wait=False)
    if app.state.redis:
        await app.state.redis.close()
    if app.state.engine:
        await app.state.engine.dispose()
    log.info("shutdown_complete")


def create_app() -> FastAPI:
    _configure_logging()

    app = FastAPI(
        title=settings.app_title,
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs" if settings.app_env == "development" else None,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins.split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Upload-Offset", "Upload-Length", "Location", "Tus-Resumable"],
    )

    # Error handlers
    from pdf_sku.common.middleware import register_error_handlers
    register_error_handlers(app)

    # ─── Health endpoint (always available) ───
    @app.get("/api/v1/health")
    async def health():
        services = getattr(app.state, "services_ready", {})
        all_ok = all(services.values()) if services else False
        return JSONResponse(
            status_code=200 if all_ok else 503,
            content={"status": "healthy" if all_ok else "degraded", "services": services},
        )

    # ─── Routers ───
    from pdf_sku.auth.router import router as auth_router
    from pdf_sku.gateway.router import router as gateway_router
    from pdf_sku.config.router import router as config_router
    from pdf_sku.collaboration.router import router as collab_router
    from pdf_sku.feedback.router import router as feedback_router

    app.include_router(auth_router)  # /api/v1/auth/*
    app.include_router(gateway_router, prefix="/api/v1")
    app.include_router(config_router)  # already has /api/v1/config prefix
    app.include_router(collab_router)  # already has /api/v1 prefix
    app.include_router(feedback_router)  # already has /api/v1 prefix

    return app
