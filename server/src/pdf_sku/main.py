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
    from pdf_sku.common.database import init_db
    import sqlalchemy
    try:
        engine, session_factory_ref = init_db(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            echo=settings.sql_echo,
        )
        # Test connection
        async with engine.connect() as conn:
            await conn.execute(sqlalchemy.text("SELECT 1"))
        # Auto-create new tables (e.g. llm_accounts)
        from pdf_sku.common.database import ensure_tables
        await ensure_tables(engine)
        app.state.engine = engine
        app.state.session_factory = session_factory_ref
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

            # LLM Clients + Provider Entries
            # Naming: model_name (直连) | model_name.proxy_host (代理)
            from pdf_sku.llm_adapter.client.registry import register as register_client
            from pdf_sku.llm_adapter.provider_config import (
                LLMProviderEntry, merge_provider_entries,
            )
            from pdf_sku.llm_adapter.client.openai_compat import OpenAICompatClient
            from pdf_sku.llm_adapter.account_service import (
                create_account, account_exists, get_account_api_key,
            )
            jwt_secret = settings.jwt_secret_key

            provider_entries: list[LLMProviderEntry] = []
            priority_counter = 0

            def _model_short_name(model: str) -> str:
                """Extract short model name: 'google/gemini-2.5-flash' → 'gemini-2.5-flash'"""
                return model.split("/")[-1] if "/" in model else model

            def _register_openai_compat(name, api_key, api_base, model, provider_name, timeout):
                client = OpenAICompatClient(
                    api_key=api_key, api_base=api_base, model=model,
                    provider_name=provider_name, timeout=timeout,
                )
                register_client(name, client)
                return client

            # ── Seed LLM accounts from .env ──
            async def _seed_account(acct_name: str, ptype: str, api_base: str, api_key: str):
                """Create seed account in DB if not exists."""
                if not api_key or not jwt_secret:
                    return
                async with session_factory() as seed_db:
                    try:
                        if not await account_exists(seed_db, acct_name):
                            await create_account(seed_db, acct_name, ptype, api_base, api_key, jwt_secret)
                            await seed_db.commit()
                            log.info("llm_account_seeded", name=acct_name, provider_type=ptype)
                        else:
                            log.info("llm_account_exists", name=acct_name)
                    except Exception as e:
                        await seed_db.rollback()
                        log.warning("llm_account_seed_failed", name=acct_name, error=str(e))

            # Seed accounts
            if settings.gemini_api_key:
                acct_name = _extract_proxy_name(settings.gemini_api_base) if settings.gemini_api_base else "gemini-direct"
                await _seed_account(acct_name, "gemini", settings.gemini_api_base, settings.gemini_api_key)
            if settings.qwen_api_key:
                acct_name = _extract_proxy_name(settings.qwen_api_base) if settings.qwen_api_base else "qwen-direct"
                await _seed_account(acct_name, "qwen", settings.qwen_api_base, settings.qwen_api_key)
            if settings.openrouter_api_key:
                await _seed_account("openrouter", "openrouter", "https://openrouter.ai/api", settings.openrouter_api_key)

            # ── Gemini (通过 api_base 判断直连/代理) ──
            gemini_account_name = ""
            if settings.gemini_api_key:
                gemini_account_name = _extract_proxy_name(settings.gemini_api_base) if settings.gemini_api_base else "gemini-direct"
                model_name = _model_short_name(settings.gemini_model)
                if settings.gemini_api_base:
                    proxy_host = _extract_proxy_name(settings.gemini_api_base)
                    client_name = f"{model_name}.{proxy_host}"
                    _register_openai_compat(
                        client_name, settings.gemini_api_key,
                        settings.gemini_api_base, settings.gemini_model,
                        proxy_host, settings.llm_timeout_seconds,
                    )
                    provider_entries.append(LLMProviderEntry(
                        name=client_name, provider_type="gemini",
                        access_mode="proxy", proxy_service=proxy_host,
                        model=settings.gemini_model, priority=priority_counter,
                        account_name=gemini_account_name,
                    ))
                else:
                    client_name = model_name
                    from pdf_sku.llm_adapter.client.gemini import GeminiClient
                    register_client(client_name, GeminiClient(
                        api_key=settings.gemini_api_key,
                        model=settings.gemini_model,
                        timeout=settings.llm_timeout_seconds,
                    ))
                    provider_entries.append(LLMProviderEntry(
                        name=client_name, provider_type="gemini",
                        access_mode="direct", model=settings.gemini_model,
                        priority=priority_counter,
                        account_name=gemini_account_name,
                    ))
                # Legacy alias for backward compat
                _register_openai_compat(
                    "gemini", settings.gemini_api_key,
                    settings.gemini_api_base or "https://generativelanguage.googleapis.com",
                    settings.gemini_model,
                    _extract_proxy_name(settings.gemini_api_base) if settings.gemini_api_base else "google",
                    settings.llm_timeout_seconds,
                )
                priority_counter += 1
                log.info("llm_registered", name=client_name,
                         model=settings.gemini_model,
                         via=settings.gemini_api_base or "direct",
                         account=gemini_account_name)

            # ── Qwen (通过 api_base 判断直连/代理) ──
            qwen_account_name = ""
            if settings.qwen_api_key:
                qwen_account_name = _extract_proxy_name(settings.qwen_api_base) if settings.qwen_api_base else "qwen-direct"
                model_name = _model_short_name(settings.qwen_model)
                if settings.qwen_api_base:
                    proxy_host = _extract_proxy_name(settings.qwen_api_base)
                    client_name = f"{model_name}.{proxy_host}"
                    _register_openai_compat(
                        client_name, settings.qwen_api_key,
                        settings.qwen_api_base, settings.qwen_model,
                        proxy_host, settings.llm_timeout_seconds,
                    )
                    provider_entries.append(LLMProviderEntry(
                        name=client_name, provider_type="qwen",
                        access_mode="proxy", proxy_service=proxy_host,
                        model=settings.qwen_model, priority=priority_counter,
                        account_name=qwen_account_name,
                    ))
                else:
                    client_name = model_name
                    from pdf_sku.llm_adapter.client.qwen import QwenClient
                    register_client(client_name, QwenClient(
                        api_key=settings.qwen_api_key,
                        model=settings.qwen_model,
                        timeout=settings.llm_timeout_seconds,
                    ))
                    provider_entries.append(LLMProviderEntry(
                        name=client_name, provider_type="qwen",
                        access_mode="direct", model=settings.qwen_model,
                        priority=priority_counter,
                        account_name=qwen_account_name,
                    ))
                # Legacy alias
                register_client("qwen", _register_openai_compat(
                    "qwen", settings.qwen_api_key,
                    settings.qwen_api_base or "https://dashscope.aliyuncs.com/compatible-mode",
                    settings.qwen_model, "dashscope",
                    settings.llm_timeout_seconds,
                ))
                priority_counter += 1
                log.info("llm_registered", name=client_name,
                         model=settings.qwen_model,
                         via=settings.qwen_api_base or "direct",
                         account=qwen_account_name)

            # ── OpenRouter (模型名从 openrouter_model 推断) ──
            if settings.openrouter_api_key and settings.openrouter_model:
                model_name = _model_short_name(settings.openrouter_model)
                client_name = f"{model_name}.openrouter"
                _register_openai_compat(
                    client_name, settings.openrouter_api_key,
                    "https://openrouter.ai/api", settings.openrouter_model,
                    "openrouter.ai", settings.llm_timeout_seconds,
                )
                # Determine provider_type from model path
                or_prefix = settings.openrouter_model.split("/")[0] if "/" in settings.openrouter_model else "unknown"
                provider_type_map = {"google": "gemini", "qwen": "qwen", "anthropic": "claude", "deepseek": "deepseek"}
                provider_type = provider_type_map.get(or_prefix, or_prefix)
                provider_entries.append(LLMProviderEntry(
                    name=client_name, provider_type=provider_type,
                    access_mode="proxy", proxy_service="openrouter",
                    model=settings.openrouter_model, priority=priority_counter,
                    account_name="openrouter",
                ))
                # Legacy alias
                register_client("openrouter", _register_openai_compat(
                    "openrouter", settings.openrouter_api_key,
                    "https://openrouter.ai/api", settings.openrouter_model,
                    "openrouter.ai", settings.llm_timeout_seconds,
                ))
                priority_counter += 1
                log.info("llm_registered", name=client_name,
                         model=settings.openrouter_model,
                         account="openrouter")

            # ── Cross-provider combinations from DB accounts ──
            # Register extra providers that are not covered by .env 1:1 mapping.
            # Each combines an existing DB account with a different model/endpoint.

            # 1) Gemini direct (official API) — account: gemini-direct
            if not any(e.name == "gemini-2.5-flash" for e in provider_entries):
                try:
                    async with session_factory() as _db:
                        gd_key, gd_base = await get_account_api_key(_db, "gemini-direct", jwt_secret)
                    # Use Google official OpenAI-compatible endpoint
                    gd_api_base = gd_base or "https://generativelanguage.googleapis.com/v1beta/openai"
                    gd_name = "gemini-2.5-flash"
                    _register_openai_compat(
                        gd_name, gd_key, gd_api_base,
                        settings.gemini_model, "google",
                        settings.llm_timeout_seconds,
                    )
                    provider_entries.append(LLMProviderEntry(
                        name=gd_name, provider_type="gemini",
                        access_mode="direct", model=settings.gemini_model,
                        priority=priority_counter, account_name="gemini-direct",
                    ))
                    priority_counter += 1
                    log.info("llm_registered", name=gd_name, account="gemini-direct", via="direct")
                except Exception as e:
                    log.warning("gemini_direct_skip", error=str(e))

            # 2) Qwen via laozhang.ai proxy — account: api.laozhang.ai
            try:
                async with session_factory() as _db:
                    lz_key, lz_base = await get_account_api_key(_db, "api.laozhang.ai", jwt_secret)
                if lz_key and lz_base:
                    qwen_lz_name = f"{_model_short_name(settings.qwen_model)}.{_extract_proxy_name(lz_base)}"
                    if not any(e.name == qwen_lz_name for e in provider_entries):
                        _register_openai_compat(
                            qwen_lz_name, lz_key, lz_base,
                            settings.qwen_model, _extract_proxy_name(lz_base),
                            settings.llm_timeout_seconds,
                        )
                        provider_entries.append(LLMProviderEntry(
                            name=qwen_lz_name, provider_type="qwen",
                            access_mode="proxy", proxy_service=_extract_proxy_name(lz_base),
                            model=settings.qwen_model, priority=priority_counter,
                            account_name="api.laozhang.ai",
                        ))
                        priority_counter += 1
                        log.info("llm_registered", name=qwen_lz_name, account="api.laozhang.ai")
            except Exception as e:
                log.warning("qwen_laozhang_skip", error=str(e))

            # 3) Qwen via OpenRouter — account: openrouter
            try:
                async with session_factory() as _db:
                    or_key, or_base = await get_account_api_key(_db, "openrouter", jwt_secret)
                if or_key:
                    qwen_or_model = "qwen/qwen2.5-vl-72b-instruct"
                    qwen_or_name = f"{_model_short_name(qwen_or_model)}.openrouter"
                    if not any(e.name == qwen_or_name for e in provider_entries):
                        _register_openai_compat(
                            qwen_or_name, or_key,
                            or_base or "https://openrouter.ai/api",
                            qwen_or_model, "openrouter.ai",
                            settings.llm_timeout_seconds,
                        )
                        provider_entries.append(LLMProviderEntry(
                            name=qwen_or_name, provider_type="qwen",
                            access_mode="proxy", proxy_service="openrouter",
                            model=qwen_or_model, priority=priority_counter,
                            account_name="openrouter",
                        ))
                        priority_counter += 1
                        log.info("llm_registered", name=qwen_or_name, account="openrouter")
            except Exception as e:
                log.warning("qwen_openrouter_skip", error=str(e))

            # 4) Gemini preview models via laozhang.ai + OpenRouter
            _GEMINI_PREVIEW_MODELS = [
                "gemini-3-flash-preview",
                "gemini-3-pro-preview",
                "gemini-3.1-pro-preview",
            ]

            # laozhang.ai
            try:
                async with session_factory() as _db:
                    lz_key2, lz_base2 = await get_account_api_key(_db, "api.laozhang.ai", jwt_secret)
                if lz_key2 and lz_base2:
                    lz_host = _extract_proxy_name(lz_base2)
                    for gm in _GEMINI_PREVIEW_MODELS:
                        cname = f"{gm}.{lz_host}"
                        if not any(e.name == cname for e in provider_entries):
                            _register_openai_compat(
                                cname, lz_key2, lz_base2, gm,
                                lz_host, settings.llm_timeout_seconds,
                            )
                            provider_entries.append(LLMProviderEntry(
                                name=cname, provider_type="gemini",
                                access_mode="proxy", proxy_service=lz_host,
                                model=gm, priority=priority_counter,
                                account_name="api.laozhang.ai",
                            ))
                            priority_counter += 1
                            log.info("llm_registered", name=cname, account="api.laozhang.ai")
            except Exception as e:
                log.warning("gemini_preview_laozhang_skip", error=str(e))

            # OpenRouter (model path needs google/ prefix)
            try:
                async with session_factory() as _db:
                    or_key2, or_base2 = await get_account_api_key(_db, "openrouter", jwt_secret)
                if or_key2:
                    or_api = or_base2 or "https://openrouter.ai/api"
                    for gm in _GEMINI_PREVIEW_MODELS:
                        or_model = f"google/{gm}"
                        cname = f"{gm}.openrouter"
                        if not any(e.name == cname for e in provider_entries):
                            _register_openai_compat(
                                cname, or_key2, or_api, or_model,
                                "openrouter.ai", settings.llm_timeout_seconds,
                            )
                            provider_entries.append(LLMProviderEntry(
                                name=cname, provider_type="gemini",
                                access_mode="proxy", proxy_service="openrouter",
                                model=or_model, priority=priority_counter,
                                account_name="openrouter",
                            ))
                            priority_counter += 1
                            log.info("llm_registered", name=cname, account="openrouter")
            except Exception as e:
                log.warning("gemini_preview_openrouter_skip", error=str(e))

            # 5) Qwen3-VL models via direct(DashScope) + laozhang.ai + OpenRouter
            _QWEN3_VL_DASHSCOPE = ["qwen3-vl-plus", "qwen3-vl-flash"]
            _QWEN3_VL_OPENROUTER = {
                "qwen3-vl-plus": "qwen/qwen3-vl-235b-a22b-instruct",
                "qwen3-vl-flash": "qwen/qwen3-vl-30b-a3b-instruct",
            }

            # DashScope direct — account: qwen-direct
            try:
                async with session_factory() as _db:
                    qd_key, qd_base = await get_account_api_key(_db, "qwen-direct", jwt_secret)
                if qd_key:
                    qd_api = qd_base or "https://dashscope.aliyuncs.com/compatible-mode"
                    for qm in _QWEN3_VL_DASHSCOPE:
                        if not any(e.name == qm for e in provider_entries):
                            _register_openai_compat(
                                qm, qd_key, qd_api, qm,
                                "dashscope", settings.llm_timeout_seconds,
                            )
                            provider_entries.append(LLMProviderEntry(
                                name=qm, provider_type="qwen",
                                access_mode="direct", model=qm,
                                priority=priority_counter, account_name="qwen-direct",
                            ))
                            priority_counter += 1
                            log.info("llm_registered", name=qm, account="qwen-direct", via="direct")
            except Exception as e:
                log.warning("qwen3vl_direct_skip", error=str(e))

            # laozhang.ai
            try:
                async with session_factory() as _db:
                    lz_key3, lz_base3 = await get_account_api_key(_db, "api.laozhang.ai", jwt_secret)
                if lz_key3 and lz_base3:
                    lz_host3 = _extract_proxy_name(lz_base3)
                    for qm in _QWEN3_VL_DASHSCOPE:
                        cname = f"{qm}.{lz_host3}"
                        if not any(e.name == cname for e in provider_entries):
                            _register_openai_compat(
                                cname, lz_key3, lz_base3, qm,
                                lz_host3, settings.llm_timeout_seconds,
                            )
                            provider_entries.append(LLMProviderEntry(
                                name=cname, provider_type="qwen",
                                access_mode="proxy", proxy_service=lz_host3,
                                model=qm, priority=priority_counter,
                                account_name="api.laozhang.ai",
                            ))
                            priority_counter += 1
                            log.info("llm_registered", name=cname, account="api.laozhang.ai")
            except Exception as e:
                log.warning("qwen3vl_laozhang_skip", error=str(e))

            # OpenRouter
            try:
                async with session_factory() as _db:
                    or_key3, or_base3 = await get_account_api_key(_db, "openrouter", jwt_secret)
                if or_key3:
                    or_api3 = or_base3 or "https://openrouter.ai/api"
                    for qm_short, qm_full in _QWEN3_VL_OPENROUTER.items():
                        cname = f"{qm_short}.openrouter"
                        if not any(e.name == cname for e in provider_entries):
                            _register_openai_compat(
                                cname, or_key3, or_api3, qm_full,
                                "openrouter.ai", settings.llm_timeout_seconds,
                            )
                            provider_entries.append(LLMProviderEntry(
                                name=cname, provider_type="qwen",
                                access_mode="proxy", proxy_service="openrouter",
                                model=qm_full, priority=priority_counter,
                                account_name="openrouter",
                            ))
                            priority_counter += 1
                            log.info("llm_registered", name=cname, account="openrouter")
            except Exception as e:
                log.warning("qwen3vl_openrouter_skip", error=str(e))

            # Merge with Redis (preserves user-adjusted priority/enabled)
            if provider_entries:
                provider_entries = await merge_provider_entries(redis, provider_entries)
                log.info("llm_providers_merged", count=len(provider_entries))

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
                budget_guard=BudgetGuard(redis) if (settings.gemini_api_key or settings.qwen_api_key or getattr(settings, 'openrouter_api_key', None)) else None,
                rate_limiter=RateLimiter(redis) if (settings.gemini_api_key or settings.qwen_api_key or getattr(settings, 'openrouter_api_key', None)) else None,
                default_client_name=settings.default_llm_client or (provider_entries[0].name if provider_entries else "gemini"),
                redis=redis,
            )
            deps.llm_service = llm_service

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
                redis=app.state.redis,
            )

            app.state.orchestrator = orchestrator

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

            # 定时恢复: 每60秒扫描页面全部终态但 Job 仍卡在 PROCESSING 的任务并自动终态
            async def _stuck_job_recovery_loop():
                from sqlalchemy import select as _select
                from pdf_sku.common.models import PDFJob as _PDFJob, Page as _Page
                from pdf_sku.common.enums import PageStatus as _PageStatus

                _terminal = {
                    _PageStatus.AI_COMPLETED.value,
                    _PageStatus.HUMAN_COMPLETED.value,
                    _PageStatus.IMPORTED_CONFIRMED.value,
                    _PageStatus.IMPORTED_ASSUMED.value,
                    _PageStatus.BLANK.value,
                    _PageStatus.AI_FAILED.value,
                    _PageStatus.IMPORT_FAILED.value,
                    _PageStatus.DEAD_LETTER.value,
                    _PageStatus.SKIPPED.value,
                }

                while True:
                    try:
                        async with session_factory() as rdb:
                            jobs = (await rdb.execute(
                                _select(_PDFJob).where(
                                    _PDFJob.status.in_(["PROCESSING", "PARTIAL_FAILED"])
                                )
                            )).scalars().all()

                            for stuck_job in jobs:
                                pages = (await rdb.execute(
                                    _select(_Page.status).where(_Page.job_id == stuck_job.job_id)
                                )).scalars().all()
                                if pages and all(s in _terminal for s in pages):
                                    log.info("recovering_stuck_job", job_id=str(stuck_job.job_id))
                                    async with session_factory() as fin_db:
                                        fresh = (await fin_db.execute(
                                            _select(_PDFJob).where(_PDFJob.job_id == stuck_job.job_id)
                                        )).scalar_one()
                                        await orchestrator._finalize_job(fin_db, fresh)
                                        await fin_db.commit()
                                    log.info("stuck_job_recovered",
                                             job_id=str(stuck_job.job_id),
                                             new_status=fresh.status)
                    except Exception as _e:
                        log.warning("stuck_job_recovery_failed", error=str(_e))
                    await asyncio.sleep(60)

            bg_tasks.append(asyncio.create_task(_stuck_job_recovery_loop()))
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


def _get_version() -> str:
    try:
        from importlib.metadata import version
        return version("pdf-sku")
    except Exception:
        return "0.3.2-dev"


def _extract_proxy_name(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).hostname or "proxy"


def create_app() -> FastAPI:
    _configure_logging()

    app = FastAPI(
        title=settings.app_title,
        version=_get_version(),
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
