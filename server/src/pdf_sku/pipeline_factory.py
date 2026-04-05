"""Pipeline 运行时选择工厂。"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from typing import Any

import structlog

from pdf_sku.settings import settings

logger = structlog.get_logger()

_SUPPORTED_IMPLEMENTATIONS = {"legacy", "v2"}


def normalize_pipeline_implementation(value: str | None) -> str:
    """标准化 pipeline 实现名，非法值回退到 legacy。"""
    normalized = (value or settings.pipeline_implementation or "legacy").strip().lower()
    if normalized not in _SUPPORTED_IMPLEMENTATIONS:
        logger.warning(
            "invalid_pipeline_implementation",
            requested=value,
            configured=settings.pipeline_implementation,
            fallback="legacy",
        )
        return "legacy"
    return normalized


def build_page_processor(
    *,
    llm_service: Any = None,
    process_pool: ProcessPoolExecutor | None = None,
    config_provider: Any = None,
    pipeline_implementation: str | None = None,
    _legacy_cls: type | None = None,
    _v2_cls: type | None = None,
):
    """按配置构建页面处理器。"""
    implementation = normalize_pipeline_implementation(pipeline_implementation)

    if implementation == "v2":
        page_processor_cls = _v2_cls
        if page_processor_cls is None:
            from pdf_sku.pipeline_v2.page_processor import PageProcessor as page_processor_cls
    else:
        page_processor_cls = _legacy_cls
        if page_processor_cls is None:
            from pdf_sku.pipeline.page_processor import PageProcessor as page_processor_cls

    logger.info("build_page_processor", implementation=implementation)
    return page_processor_cls(
        llm_service=llm_service,
        process_pool=process_pool,
        config_provider=config_provider,
    )
