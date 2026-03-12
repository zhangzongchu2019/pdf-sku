"""
merge_sku_specs.py – 合并同商品不同规格的 SKU：
对同一 job 中同一页面上相同 product_id 的多个活跃 SKU，
将它们的 size 规格（拼接 variant_label）合并到主 SKU，
将所有 SKU（含历史已废弃）的图片绑定也合并到主 SKU，
并将其余活跃 SKU 标记为 superseded。

用法：
    python scripts/merge_sku_specs.py <job_id> [--dry-run]
"""
import asyncio
import sys
import argparse
import copy
import uuid as uuid_mod
from collections import defaultdict

sys.path.insert(0, "src")

from pdf_sku.common.database import init_db
from pdf_sku.common.models import SKU, PDFJob, Page, SKUImageBinding
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

DB_URL = "postgresql+asyncpg://pdfsku:pdfsku@localhost:5432/pdfsku"

SIZE_KEYS = ["size", "尺寸", "规格", "specification", "spec"]


def get_size(attrs: dict) -> str | None:
    for k in SIZE_KEYS:
        v = attrs.get(k)
        if v and isinstance(v, str):
            return v
    return None


async def merge_skus_for_job(job_id: str, dry_run: bool, session: AsyncSession) -> None:
    job_uuid = uuid_mod.UUID(job_id) if isinstance(job_id, str) else job_id

    result = await session.execute(select(PDFJob).where(PDFJob.job_id == job_uuid))
    job = result.scalar_one_or_none()
    if not job:
        print(f"[ERROR] Job {job_id} not found")
        return
    print(f"[INFO] Job: {job.job_id}  status={job.status}  file={job.source_file}")

    result = await session.execute(
        select(SKU).where(SKU.job_id == job_uuid).order_by(SKU.page_number, SKU.sku_id)
    )
    all_skus: list[SKU] = result.scalars().all()
    active_count = sum(1 for s in all_skus if not s.superseded)
    print(f"[INFO] SKU 总数：{len(all_skus)}（活跃 {active_count}，已废弃 {len(all_skus) - active_count}）")

    # 活跃 SKU 分组 → 确定哪些需要合并（保证幂等：已合并的只剩主 SKU，不会重复计算）
    active_groups: dict[tuple, list[SKU]] = defaultdict(list)
    for sku in all_skus:
        if sku.product_id and not sku.superseded:
            active_groups[(sku.page_number, sku.product_id)].append(sku)

    # 全量 SKU 分组（含 superseded）→ 用于收集历史遗留的图片绑定
    all_groups: dict[tuple, list[SKU]] = defaultdict(list)
    for sku in all_skus:
        if sku.product_id:
            all_groups[(sku.page_number, sku.product_id)].append(sku)

    # 预取所有 is_latest binding
    result = await session.execute(
        select(SKUImageBinding).where(
            SKUImageBinding.job_id == job_uuid,
            SKUImageBinding.is_latest.is_(True),
        )
    )
    all_bindings = result.scalars().all()
    bindings_by_sku: dict[str, list[SKUImageBinding]] = defaultdict(list)
    for b in all_bindings:
        bindings_by_sku[b.sku_id].append(b)

    merge_count = 0
    superseded_count = 0
    binding_added_count = 0
    # 全局跟踪本次会话中已添加的 (sku_id, image_id)，避免重复插入
    added_pairs: set[tuple[str, str]] = set()

    for key, active_group in sorted(active_groups.items()):
        if len(active_group) <= 1:
            continue

        page, product_id = key
        active_sorted = sorted(active_group, key=lambda s: s.sku_id)
        primary = active_sorted[0]
        others_active = active_sorted[1:]

        # ── 1. 规格合并（仅活跃 SKU，避免重复） ──────────────────────────
        all_sizes: list[str] = []
        for sku in active_sorted:
            sz = get_size(sku.attributes)
            if not sz:
                continue
            label = (sku.variant_label or "").strip()
            entry = f"{label}: {sz}" if label else sz
            if entry not in all_sizes:
                all_sizes.append(entry)

        # ── 2. 图片绑定合并（全量：含历史已废弃 SKU 的绑定） ─────────────
        # 主 SKU 当前已有的 image_id
        primary_image_ids: set[str] = {b.image_id for b in bindings_by_sku[primary.sku_id]}
        max_rank = max((b.rank for b in bindings_by_sku[primary.sku_id]), default=0)

        # 全量组（含 superseded）中除主 SKU 外的所有成员
        all_group_skus = all_groups[key]
        others_all = [s for s in all_group_skus if s.sku_id != primary.sku_id]

        new_bindings: list[SKUImageBinding] = []
        for other in others_all:
            for b in bindings_by_sku[other.sku_id]:
                if b.image_id not in primary_image_ids and (primary.sku_id, b.image_id) not in added_pairs:
                    primary_image_ids.add(b.image_id)
                    added_pairs.add((primary.sku_id, b.image_id))
                    max_rank += 1
                    new_bindings.append(SKUImageBinding(
                        sku_id=primary.sku_id,
                        image_id=b.image_id,
                        job_id=job_uuid,
                        image_role=b.image_role,
                        binding_method=b.binding_method,
                        binding_confidence=b.binding_confidence,
                        is_ambiguous=b.is_ambiguous,
                        rank=max_rank,
                        revision=b.revision,
                        is_latest=True,
                    ))

        print(f"\n[MERGE] Page {page} / product_id={product_id} ({len(active_group)} 活跃 SKUs → 1)")
        print(f"  主 SKU: {primary.sku_id}")
        print(f"  合并规格: {all_sizes}")
        print(f"  废弃 SKU: {[s.sku_id for s in others_active]}")
        if new_bindings:
            print(f"  新增图片绑定: {[nb.image_id for nb in new_bindings]}")
        else:
            print(f"  图片绑定: 无新增")

        if not dry_run:
            new_attrs = copy.deepcopy(primary.attributes)
            size_key = next((k for k in SIZE_KEYS if k in new_attrs), SIZE_KEYS[0])
            new_attrs[size_key] = all_sizes
            primary.attributes = new_attrs
            session.add(primary)

            for nb in new_bindings:
                session.add(nb)

            for other in others_active:
                other.superseded = True
                session.add(other)

        merge_count += 1
        superseded_count += len(others_active)
        binding_added_count += len(new_bindings)

    # ── 补录：修复历史合并遗留的图片绑定 ────────────────────────────────────
    # 适用场景：组内只剩 1 个活跃 SKU（主 SKU），但 superseded SKU 的图片尚未转移
    fix_binding_count = 0
    for key, all_group_skus in sorted(all_groups.items()):
        page, product_id = key
        active_in_group = [s for s in all_group_skus if not s.superseded]
        if len(active_in_group) != 1:
            continue  # 多活跃→已在上方处理；0 活跃→异常，跳过
        primary = active_in_group[0]
        others_superseded = [s for s in all_group_skus if s.superseded]
        if not others_superseded:
            continue

        primary_image_ids: set[str] = {b.image_id for b in bindings_by_sku[primary.sku_id]}
        max_rank = max((b.rank for b in bindings_by_sku[primary.sku_id]), default=0)

        new_bindings: list[SKUImageBinding] = []
        for other in others_superseded:
            for b in bindings_by_sku[other.sku_id]:
                if b.image_id not in primary_image_ids and (primary.sku_id, b.image_id) not in added_pairs:
                    primary_image_ids.add(b.image_id)
                    added_pairs.add((primary.sku_id, b.image_id))
                    max_rank += 1
                    new_bindings.append(SKUImageBinding(
                        sku_id=primary.sku_id,
                        image_id=b.image_id,
                        job_id=job_uuid,
                        image_role=b.image_role,
                        binding_method=b.binding_method,
                        binding_confidence=b.binding_confidence,
                        is_ambiguous=b.is_ambiguous,
                        rank=max_rank,
                        revision=b.revision,
                        is_latest=True,
                    ))

        if new_bindings:
            print(
                f"\n[FIX-BINDING] Page {page} / product_id={product_id} "
                f"主 SKU={primary.sku_id}"
            )
            print(f"  补录图片绑定: {[nb.image_id for nb in new_bindings]}")
            if not dry_run:
                for nb in new_bindings:
                    session.add(nb)
            fix_binding_count += len(new_bindings)

    binding_added_count += fix_binding_count

    if not dry_run:
        await session.commit()
        print(
            f"\n[DONE] 已提交：合并组 {merge_count} 个，"
            f"废弃 SKU {superseded_count} 个，"
            f"新增图片绑定 {binding_added_count} 条（其中补录 {fix_binding_count} 条）"
        )

        print("[INFO] 同步 sku_count 计数器...")
        result = await session.execute(select(Page).where(Page.job_id == job_uuid))
        pages = result.scalars().all()
        for page in pages:
            r = await session.execute(
                select(func.count()).where(
                    SKU.job_id == job_uuid,
                    SKU.page_number == page.page_number,
                    SKU.superseded.is_(False),
                )
            )
            real = r.scalar()
            if page.sku_count != real:
                page.sku_count = real
                session.add(page)

        r = await session.execute(
            select(func.count()).where(SKU.job_id == job_uuid, SKU.superseded.is_(False))
        )
        real_total = r.scalar()
        result = await session.execute(select(PDFJob).where(PDFJob.job_id == job_uuid))
        job_obj = result.scalar_one_or_none()
        if job_obj and job_obj.total_skus != real_total:
            job_obj.total_skus = real_total
            session.add(job_obj)

        await session.commit()
        print(f"[INFO] total_skus 更新为 {real_total}")
    else:
        print(
            f"\n[DRY-RUN] 将合并组 {merge_count} 个，"
            f"废弃 SKU {superseded_count} 个，"
            f"新增图片绑定 {binding_added_count} 条（其中补录 {fix_binding_count} 条）（未修改数据库）"
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description="合并同商品不同规格 SKU")
    parser.add_argument("job_id", help="要处理的 PDF job UUID")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划，不修改数据库")
    args = parser.parse_args()

    engine, session_factory = init_db(DB_URL)
    async with session_factory() as session:
        await merge_skus_for_job(args.job_id, args.dry_run, session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
