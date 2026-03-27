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

# 数据目录: 相对于 server/ 目录
_SERVER_DIR = Path(__file__).resolve().parent.parent.parent.parent
CACHE_DIR = _SERVER_DIR / "data" / "benchmark_cache"
HISTORY_DIR = _SERVER_DIR / "data" / "benchmark_history"
def _get_image_dir() -> Path:
    from pdf_sku.settings import settings
    return Path(settings.benchmark_image_dir)
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


def _is_blank_image(data: bytes, threshold: float = 240) -> bool:
    """检测纯白/纯色空白占位图（PDF排版用，无实际产品内容）。"""
    try:
        from PIL import Image
        import numpy as np
        import io
        img = Image.open(io.BytesIO(data)).convert("RGB")
        arr = np.array(img)
        if arr.mean() <= threshold:
            return False
        white_ratio = (arr > threshold).all(axis=2).sum() / (arr.shape[0] * arr.shape[1])
        return white_ratio > 0.95
    except Exception:
        return False


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
) -> dict[str, list[str]]:
    """保存页面图片，返回 sku_id → 图片文件名列表映射。

    包括：
    - 通过 binding 关联到 SKU 的图片
    - search_eligible 的 composite 合成图（瓦片拼合后的完整产品图）
    """
    img_map = {img.image_id: img for img in result.images if img.data}
    if not img_map:
        return {}

    # 保存所有有数据的 search_eligible 图片到磁盘（过滤碎片和空白图）
    saved_files: dict[str, str] = {}  # image_id → filename
    for img in result.images:
        if not img.data or not img.search_eligible:
            continue
        if img.is_fragmented:  # 跳过瓦片碎片，只保留 composite 合成图
            continue
        if _is_blank_image(img.data):  # 跳过纯白/纯色空白占位图
            continue
        # image_id 可能已包含页码前缀 (如 p1_img0)，避免重复
        img_id = img.image_id or f"p{page_no}_img"
        fname = f"{img_id}.jpg" if img_id.startswith("p") else f"p{page_no}_{img_id}.jpg"
        fpath = image_dir / fname
        if not fpath.exists():
            fpath.write_bytes(img.data)
        saved_files[img.image_id] = fname

    # 建立 sku_id → 文件名列表 映射
    sku_images: dict[str, list[str]] = {}
    bound_image_ids: set[str] = set()

    # Step 1: 使用 binding 结果精准关联
    if result.bindings:
        for binding in result.bindings:
            if binding.is_ambiguous or not binding.image_id:
                continue
            fname = saved_files.get(binding.image_id)
            if fname:
                sku_images.setdefault(binding.sku_id, []).append(fname)
                bound_image_ids.add(binding.image_id)

    # Step 2: 页面级兜底 — 对未绑定的 SKU 按页面规则补充关联
    if saved_files and result.skus:
        all_fnames = list(saved_files.values())
        unbound_fnames = [
            fname for img_id, fname in saved_files.items()
            if img_id not in bound_image_ids
        ]
        unbound_sku_ids = [
            s.sku_id for s in result.skus
            if s.sku_id not in sku_images
        ]

        if len(result.skus) == 1:
            # 单 SKU 页面: 所有图片归该 SKU
            sku_images[result.skus[0].sku_id] = all_fnames
        elif unbound_sku_ids and unbound_fnames:
            # 多 SKU 页面: 未绑定的 SKU 共享未绑定的图片
            for sid in unbound_sku_ids:
                sku_images[sid] = list(unbound_fnames)
        elif unbound_sku_ids and not unbound_fnames and all_fnames:
            # 所有图片都已绑定，但有 SKU 没图 → 共享所有图片
            for sid in unbound_sku_ids:
                sku_images[sid] = list(all_fnames)

    return sku_images


def _consolidate_images_after_dedup(
    all_skus_flat: list[tuple[int, int, dict]],
    sku_results: list[SKUResult],
    kept_ids: set[int],
) -> None:
    """将被去重删除的 SKU 的 image_paths 合并到存活 SKU 中。"""
    # 建立存活 SKU 索引: model → dict, name → dict
    survivors_by_model: dict[str, dict] = {}
    survivors_by_name: dict[str, dict] = {}
    for (_, _, sku_dict), sr in zip(all_skus_flat, sku_results):
        if id(sr) in kept_ids:
            model = (sr.attributes.get("model_number") or "").strip().upper()
            name = (sr.attributes.get("product_name") or "").strip()
            if model:
                survivors_by_model[model] = sku_dict
            if name:
                survivors_by_name[name] = sku_dict

    # 转移被删除 SKU 的图片
    transferred = 0
    for (_, _, sku_dict), sr in zip(all_skus_flat, sku_results):
        if id(sr) in kept_ids:
            continue
        removed_images = sku_dict.get("image_paths", [])
        if not removed_images:
            continue
        model = (sr.attributes.get("model_number") or "").strip().upper()
        name = (sr.attributes.get("product_name") or "").strip()
        target = survivors_by_model.get(model) if model else None
        if not target:
            target = survivors_by_name.get(name)
        if target:
            existing = target.get("image_paths", [])
            for img in removed_images:
                if img not in existing:
                    existing.append(img)
                    transferred += 1
            target["image_paths"] = existing

    if transferred:
        logger.info("images_consolidated_after_dedup", transferred=transferred)


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

        # 图片输出目录（独立于工程源代码）
        safe_name = ds.name.replace("/", "_").replace(" ", "_")
        image_dir = _get_image_dir() / safe_name
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
                    # 保存图片并建立 sku_id → image_paths 映射
                    sku_image_map = _save_page_images(result, page_no, image_dir)

                    page_dict = _page_result_to_dict(result, page_no)

                    # 将图片相对 URL 写入 SKU
                    # 判断页面是否有文字 SKU 信息
                    has_text_sku = any(
                        (s.get("attributes", {}).get("model_number") or "").strip()
                        or (s.get("attributes", {}).get("price") or "").strip()
                        for s in page_dict["skus"]
                    )

                    for sku_dict in page_dict["skus"]:
                        sid = sku_dict.get("sku_id", "")
                        raw_paths = sku_image_map.get(sid, [])
                        sku_dict["image_paths"] = [
                            f"/images/benchmark/{safe_name}/{fname}"
                            for fname in raw_paths
                        ]
                        # 标记信息来源
                        attrs = sku_dict.get("attributes", {})
                        has_model = bool((attrs.get("model_number") or "").strip())
                        has_price = bool((attrs.get("price") or "").strip())
                        if has_model or has_price:
                            sku_dict["extraction_source"] = "text+image"
                        elif has_text_sku:
                            sku_dict["extraction_source"] = "text+image"
                        else:
                            sku_dict["extraction_source"] = "image_only"

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

            # 合并被去重 SKU 的图片到存活 SKU
            _consolidate_images_after_dedup(all_skus_flat, sku_results, kept_ids)

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

        # ═══ 组合图册: 按型号去重 (同型号不同颜色=同一产品) ═══
        if is_combo and len(all_skus_flat) > 1:
            seen: dict[str, dict] = {}  # model → first occurrence sku_dict
            for pi, page in enumerate(pages):
                new_skus = []
                for si, sku in enumerate(page.get("skus", [])):
                    attrs = sku.get("attributes", {})
                    model = (attrs.get("model_number") or "").strip().upper()
                    key = model if model else ""
                    if key and key in seen:
                        # 转移图片到存活 SKU
                        survivor = seen[key]
                        for img in sku.get("image_paths", []):
                            if img not in survivor.get("image_paths", []):
                                survivor.setdefault("image_paths", []).append(img)
                        continue
                    if key:
                        seen[key] = sku
                    new_skus.append(sku)
                page["skus"] = new_skus
                page["sku_count"] = len(new_skus)
            deduped_total = sum(len(p.get("skus", [])) for p in pages)
            if deduped_total < len(all_skus_flat):
                logger.info("combo_model_dedup_done",
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

    async def save_run_to_db(
        self,
        results: list,  # list[ComparisonResult]
        run_results: list[dict],
        *,
        run_tag: str,
        description: str = "",
        started_at: datetime | None = None,
    ) -> str:
        """将 benchmark 结果保存到数据库。返回 run_id。

        Args:
            results: compare_dataset() 返回的 ComparisonResult 列表
            run_results: 每个数据集的 pipeline 输出 dict 列表
            run_tag: 轮次标签，如 "v6", "fix-color-expand"
            description: 本轮修改说明
            started_at: 运行开始时间
        """
        import subprocess
        from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
        from pdf_sku.common.models import BenchmarkRun, BenchmarkDatasetResult
        from pdf_sku.settings import settings

        engine = create_async_engine(settings.database_url, pool_size=2)
        session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # git info
        git_commit = None
        git_branch = None
        try:
            git_commit = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], text=True, timeout=5
            ).strip()[:40]
            git_branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True, timeout=5
            ).strip()[:200]
        except Exception:
            pass

        # 汇总指标
        n = len(results)
        avg_p = sum(r.precision for r in results) / n if n else None
        avg_r = sum(r.recall for r in results) / n if n else None
        avg_f1 = sum(r.f1 for r in results) / n if n else None

        run = BenchmarkRun(
            run_tag=run_tag,
            git_commit=git_commit,
            git_branch=git_branch,
            description=description or None,
            total_datasets=n,
            avg_precision=avg_p,
            avg_recall=avg_r,
            avg_f1=avg_f1,
            config={
                "page_concurrency": PAGE_CONCURRENCY,
                "dataset_concurrency": DATASET_CONCURRENCY,
            },
            started_at=started_at or datetime.now(),
            completed_at=datetime.now(),
        )

        # 构建 run_result 查找表 (dataset_name → dict)
        rr_map = {rr.get("dataset"): rr for rr in run_results}

        for cr in results:
            rr = rr_map.get(cr.dataset_name, {})
            ds_result = BenchmarkDatasetResult(
                dataset_name=cr.dataset_name,
                pdf_path=rr.get("pdf"),
                gt_count=cr.expected_count,
                pred_count=cr.actual_count,
                matched_count=cr.matched_count,
                precision=cr.precision,
                recall=cr.recall,
                f1=cr.f1,
                fn_count=len(cr.missing_skus),
                fp_count=len(cr.extra_skus),
                elapsed_seconds=rr.get("elapsed_seconds"),
                total_pages=rr.get("total_pages"),
                details={
                    "fn_names": [
                        s.product_name or s.model_number or ""
                        for s in cr.missing_skus[:50]
                    ],
                    "fp_names": [
                        s.get("attributes", {}).get("product_name", "")
                        or s.get("attributes", {}).get("model_number", "")
                        for s in cr.extra_skus[:50]
                    ],
                },
            )
            run.dataset_results.append(ds_result)

        async with session_factory() as session:
            session.add(run)
            await session.commit()
            run_id = str(run.run_id)

        await engine.dispose()
        logger.info("benchmark_saved_to_db", run_id=run_id, run_tag=run_tag, datasets=n)
        return run_id

    def shutdown(self):
        if self._pool:
            self._pool.shutdown(wait=False)
