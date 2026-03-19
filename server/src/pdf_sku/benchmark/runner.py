"""Pipeline Runner — 批量调用 PageProcessor，结果缓存到 JSON。"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import structlog

from pdf_sku.pipeline.ir import PageResult, SKUResult, ImageInfo, BindingResult
from pdf_sku.pipeline.page_processor import PageProcessor
from pdf_sku.pipeline.extractor.sku_dedup import (
    cross_page_dedup, dedup_by_model_variant, dedup_material_variants,
)
from pdf_sku.pipeline.catalog_profiler import scan_catalog
from pdf_sku.config.service import DEFAULT_PROFILE

from .models import ReferenceDataset

logger = structlog.get_logger()

CACHE_DIR = Path("/home/zzc/pdf-sku/server/data/benchmark_cache")
HISTORY_DIR = Path("/home/zzc/pdf-sku/server/data/benchmark_history")
IMAGE_DIR = Path("/home/zzc/pdf-sku/server/data/benchmark_images")
# 页面并发数，与 Orchestrator 保持一致
# 总 LLM 并发上限 = DATASET_CONCURRENCY × PAGE_CONCURRENCY
# 建议保持 ≤ 20 避免 API 超时
PAGE_CONCURRENCY = int(os.environ.get("BENCHMARK_CONCURRENCY", "16"))
DATASET_CONCURRENCY = int(os.environ.get("BENCHMARK_DATASET_CONCURRENCY", "4"))


def archive_cache(tag: str = "") -> Path | None:
    """将当前 benchmark_cache 归档到 benchmark_history/<timestamp>_<tag>/。

    Returns:
        归档目录路径，无缓存可归档时返回 None。
    """
    if not CACHE_DIR.exists() or not any(CACHE_DIR.glob("*.json")):
        return None

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = f"_{tag}" if tag else ""
    archive_dir = HISTORY_DIR / f"{ts}{suffix}"
    archive_dir.mkdir(parents=True, exist_ok=True)

    for f in CACHE_DIR.glob("*.json"):
        shutil.copy2(f, archive_dir / f.name)

    # 同时归档报告 (如果存在)
    report_path = CACHE_DIR.parent / "benchmark_reports" / "report.md"
    if report_path.exists():
        shutil.copy2(report_path, archive_dir / "report.md")

    logger.info("cache_archived", archive=str(archive_dir),
                files=len(list(archive_dir.glob("*.json"))))
    return archive_dir


def clear_cache() -> int:
    """清空 benchmark_cache 目录。返回删除的文件数。"""
    if not CACHE_DIR.exists():
        return 0
    removed = 0
    for f in CACHE_DIR.glob("*.json"):
        f.unlink()
        removed += 1
    return removed


def list_history() -> list[Path]:
    """列出所有历史归档目录，按时间倒序。"""
    if not HISTORY_DIR.exists():
        return []
    dirs = sorted(HISTORY_DIR.iterdir(), reverse=True)
    return [d for d in dirs if d.is_dir()]


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
        "fitz_page_class": pr.fitz_page_class,
        "extraction_method": pr.extraction_method,
        "slice_count": pr.slice_count,
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


def _save_page_images(
    result: PageResult, page_no: int, image_dir: Path,
) -> dict[str, str]:
    """保存页面图片，返回 sku_id → 图片文件名映射。"""
    img_map = {img.image_id: img for img in result.images if img.data}
    if not img_map or not result.bindings:
        return {}

    sku_image: dict[str, str] = {}
    for binding in result.bindings:
        if binding.is_ambiguous or not binding.image_id:
            continue
        img = img_map.get(binding.image_id)
        if not img or not img.data:
            continue
        fname = f"p{page_no}_{binding.image_id}.jpg"
        fpath = image_dir / fname
        if not fpath.exists():
            fpath.write_bytes(img.data)
        sku_image[binding.sku_id] = fname

    return sku_image


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

        # 图册级预扫描
        catalog_profile = scan_catalog(pdf_path)

        # 图片输出目录
        safe_name = ds.name.replace("/", "_").replace(" ", "_")
        image_dir = IMAGE_DIR / safe_name
        image_dir.mkdir(parents=True, exist_ok=True)

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
                        catalog_profile=catalog_profile,
                    )
                    # 保存图片并建立 sku_id → image_path 映射
                    sku_image_map = _save_page_images(result, page_no, image_dir)

                    page_dict = _page_result_to_dict(result, page_no)

                    # 将图片路径写入 SKU
                    for sku_dict in page_dict["skus"]:
                        sid = sku_dict.get("sku_id", "")
                        sku_dict["image_path"] = sku_image_map.get(sid, "")

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

        # ═══ 跨页去重 (组合图册跳过: 每页=独立产品组合) ═══
        all_skus_flat: list[tuple[int, int, dict]] = []  # (page_idx, sku_idx, sku_dict)
        for pi, page in enumerate(pages):
            for si, sku in enumerate(page.get("skus", [])):
                all_skus_flat.append((pi, si, sku))

        is_combo = catalog_profile and catalog_profile.is_combo_catalog
        if len(all_skus_flat) > 1 and not is_combo:
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
            deduped = cross_page_dedup(sku_results, catalog_profile=catalog_profile)
            deduped = dedup_by_model_variant(deduped)
            deduped = dedup_material_variants(deduped)
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

        # ═══ 组合图册: 颜色感知去重 (同型号+同颜色才合并) ═══
        if is_combo and len(all_skus_flat) > 1:
            seen: set[str] = set()
            remove_set: set[tuple[int, int]] = set()
            for pi, page in enumerate(pages):
                new_skus = []
                for si, sku in enumerate(page.get("skus", [])):
                    attrs = sku.get("attributes", {})
                    model = (attrs.get("model_number") or "").strip().upper()
                    color = (attrs.get("color") or "").strip()
                    key = f"{model}||{color}" if model else ""
                    if key and key in seen:
                        continue
                    if key:
                        seen.add(key)
                    new_skus.append(sku)
                page["skus"] = new_skus
                page["sku_count"] = len(new_skus)
            deduped_total = sum(len(p.get("skus", [])) for p in pages)
            if deduped_total < len(all_skus_flat):
                logger.info("combo_color_dedup_done",
                            before=len(all_skus_flat), after=deduped_total)

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
