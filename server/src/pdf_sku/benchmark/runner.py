"""Pipeline Runner — 批量调用 PageProcessor，结果缓存到 JSON。"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import structlog

from pdf_sku.pipeline.ir import PageResult, SKUResult
from pdf_sku.pipeline.page_processor import PageProcessor
from pdf_sku.pipeline.extractor.sku_dedup import cross_page_dedup
from pdf_sku.config.service import DEFAULT_PROFILE

from .models import ReferenceDataset

logger = structlog.get_logger()

CACHE_DIR = Path("/home/zzc/pdf-sku/server/data/benchmark_cache")
# 页面并发数，与 Orchestrator 保持一致
# 总 LLM 并发上限 = DATASET_CONCURRENCY × PAGE_CONCURRENCY
# 建议保持 ≤ 20 避免 API 超时
PAGE_CONCURRENCY = int(os.environ.get("BENCHMARK_CONCURRENCY", "16"))
DATASET_CONCURRENCY = int(os.environ.get("BENCHMARK_DATASET_CONCURRENCY", "4"))


def _file_hash(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()[:12]


def _page_result_to_dict(pr: PageResult, page_no: int) -> dict[str, Any]:
    return {
        "page_no": page_no,
        "status": pr.status,
        "page_type": pr.page_type,
        "extraction_method": pr.extraction_method,
        "sku_count": len(pr.skus),
        "skus": [
            {
                "sku_id": s.sku_id,
                "attributes": s.attributes,
                "confidence": s.confidence,
                "validity": s.validity,
                "extraction_method": s.extraction_method,
            }
            for s in pr.skus
        ],
        "error": pr.error,
    }


class BenchmarkRunner:
    """批量运行 Pipeline 并缓存结果。"""

    def __init__(self):
        self._processor: PageProcessor | None = None
        self._pool: ProcessPoolExecutor | None = None

    async def _ensure_processor(self):
        if self._processor is not None:
            return

        from pdf_sku.main import create_llm_service
        from pdf_sku.llm_adapter.resilience.circuit_breaker import CircuitBreaker

        # Benchmark 模式: 禁用熔断器 (高阈值+短超时)，无 rate_limiter/budget
        noop_breaker = CircuitBreaker(
            failure_threshold=9999, open_timeout=1.0)

        llm_service = create_llm_service(redis=None)
        # 替换为宽松熔断器
        llm_service._circuit = noop_breaker

        self._pool = ProcessPoolExecutor(max_workers=4)

        # 创建一个无 DB 的 ConfigProvider mock
        from pdf_sku.config.service import ConfigProvider
        self._processor = PageProcessor(
            llm_service=llm_service,
            process_pool=self._pool,
            config_provider=ConfigProvider(),
        )

    def _cache_path(self, ds: ReferenceDataset) -> Path:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = ds.name.replace("/", "_").replace(" ", "_")
        return CACHE_DIR / f"{safe_name}.json"

    def load_cached(self, ds: ReferenceDataset) -> dict | None:
        p = self._cache_path(ds)
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return None

    async def run_dataset(
        self, ds: ReferenceDataset, *, force: bool = False
    ) -> dict:
        """运行单个数据集，返回结果 dict。"""
        if not ds.pdf_path or not ds.pdf_path.exists():
            return {"error": f"PDF not found: {ds.pdf_path}", "pages": []}

        # 检查缓存
        if not force:
            cached = self.load_cached(ds)
            if cached:
                logger.info("cache_hit", dataset=ds.name)
                return cached

        await self._ensure_processor()

        pdf_path = str(ds.pdf_path)
        fhash = _file_hash(ds.pdf_path)
        job_id = f"benchmark-{ds.name}"

        # 获取总页数
        import fitz
        doc = fitz.open(pdf_path)
        total_pages = doc.page_count
        doc.close()

        logger.info("run_start", dataset=ds.name, pages=total_pages,
                     concurrency=PAGE_CONCURRENCY)
        t0 = time.time()

        # 并行处理页面 (Semaphore 控制并发)
        semaphore = asyncio.Semaphore(PAGE_CONCURRENCY)
        results: dict[int, dict] = {}

        async def process_one(page_no: int):
            async with semaphore:
                try:
                    result = await self._processor.process_page(
                        job_id=job_id,
                        file_path=pdf_path,
                        page_no=page_no,
                        file_hash=fhash,
                    )
                    page_dict = _page_result_to_dict(result, page_no)
                    results[page_no] = page_dict
                    logger.info(
                        "page_done",
                        dataset=ds.name,
                        page=f"{page_no}/{total_pages}",
                        skus=len(result.skus),
                        type=result.page_type,
                    )
                except Exception as e:
                    logger.error("page_error", dataset=ds.name, page=page_no, error=str(e))
                    results[page_no] = {
                        "page_no": page_no,
                        "status": "ERROR",
                        "error": str(e),
                        "skus": [],
                    }

        await asyncio.gather(
            *[process_one(p) for p in range(1, total_pages + 1)]
        )

        # 按页码排序
        pages = [results[p] for p in sorted(results.keys())]

        # ═══ 跨页去重 ═══
        all_skus_flat: list[tuple[int, int, dict]] = []  # (page_idx, sku_idx, sku_dict)
        for pi, page in enumerate(pages):
            for si, sku in enumerate(page.get("skus", [])):
                all_skus_flat.append((pi, si, sku))

        if len(all_skus_flat) > 1:
            # 转换为 SKUResult 进行去重
            sku_results = [
                SKUResult(
                    attributes=s[2].get("attributes", {}),
                    confidence=s[2].get("confidence", 0.5),
                    extraction_method=s[2].get("extraction_method", ""),
                    sku_id=s[2].get("sku_id"),
                    validity=s[2].get("validity", "valid"),
                )
                for s in all_skus_flat
            ]
            deduped = cross_page_dedup(sku_results)
            # 找出保留的 SKU (通过 id 匹配)
            kept_ids = {id(s) for s in deduped}
            # 重建 pages 中的 skus
            remove_set: set[tuple[int, int]] = set()
            for (pi, si, _), sr in zip(all_skus_flat, sku_results):
                if id(sr) not in kept_ids:
                    remove_set.add((pi, si))
            if remove_set:
                for pi, page in enumerate(pages):
                    page["skus"] = [
                        s for si, s in enumerate(page.get("skus", []))
                        if (pi, si) not in remove_set
                    ]
                    page["sku_count"] = len(page["skus"])

        total_skus = sum(len(p.get("skus", [])) for p in pages)

        elapsed = time.time() - t0
        output = {
            "dataset": ds.name,
            "pdf": str(ds.pdf_path),
            "total_pages": total_pages,
            "total_skus": total_skus,
            "elapsed_seconds": round(elapsed, 1),
            "pages": pages,
        }

        # 写缓存
        cache_path = self._cache_path(ds)
        cache_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("run_done", dataset=ds.name, skus=total_skus, seconds=round(elapsed, 1))

        # 清理 job 缓存
        if self._processor:
            self._processor.clear_job_cache(job_id)

        return output

    def shutdown(self):
        if self._pool:
            self._pool.shutdown(wait=False)
