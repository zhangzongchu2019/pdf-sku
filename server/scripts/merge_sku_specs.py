"""
merge_sku_specs.py – 合并同商品不同规格的 SKU：
对同一 job 中同一页面上相同 product_id 的多个 SKU，
将它们的 size 规格合并到第一个 SKU（_001）中，
并将其余 SKU 标记为 superseded。

用法：
    python scripts/merge_sku_specs.py <job_id> [--dry-run]
"""
import asyncio
import sys
import argparse
import copy
from collections import defaultdict

sys.path.insert(0, "src")

from pdf_sku.common.database import init_db
from pdf_sku.common.models import SKU, PDFJob, Page
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

DB_URL = "postgresql+asyncpg://pdfsku:pdfsku@localhost:5432/pdfsku"

# 尺寸相关属性键枚举（按优先级）
SIZE_KEYS = ["size", "尺寸", "规格", "specification", "spec"]


def get_size(attrs: dict) -> str | None:
    for k in SIZE_KEYS:
        v = attrs.get(k)
        if v:
            return str(v)
    return None


async def merge_skus_for_job(job_id: str, dry_run: bool, session: AsyncSession) -> None:
    # 验证 job 存在
    result = await session.execute(select(PDFJob).where(PDFJob.job_id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        print(f"[ERROR] Job {job_id} not found")
        return
    print(f"[INFO] Job: {job.job_id}  status={job.status}  file={job.source_file}")

    # 取出所有非 superseded SKU
    result = await session.execute(
        select(SKU)
        .where(SKU.job_id == job_id, SKU.superseded.is_(False))
        .order_by(SKU.page_number, SKU.sku_id)
    )
    all_skus: list[SKU] = result.scalars().all()
    print(f"[INFO] 活跃 SKU 总数：{len(all_skus)}")

    # 按 (page_number, product_id) 分组
    groups: dict[tuple, list[SKU]] = defaultdict(list)
    for sku in all_skus:
        groups[(sku.page_number, sku.product_id)].append(sku)

    merge_count = 0
    superseded_count = 0

    for (page, product_id), group in sorted(groups.items()):
        if len(group) <= 1:
            continue  # 不需要合并

        # 按 sku_id 排序，取第一个作为主 SKU
        group_sorted = sorted(group, key=lambda s: s.sku_id)
        primary = group_sorted[0]
        others = group_sorted[1:]

        # 收集所有尺寸
        all_sizes: list[str] = []
        for sku in group_sorted:
            sz = get_size(sku.attributes)
            if sz and sz not in all_sizes:
                all_sizes.append(sz)

        print(
            f"\n[MERGE] Page {page} / product_id={product_id} "
            f"({len(group)} SKUs → 1)"
        )
        print(f"  主 SKU: {primary.sku_id}")
        print(f"  合并尺寸: {all_sizes}")
        print(f"  废弃 SKU: {[s.sku_id for s in others]}")

        if not dry_run:
            # 更新主 SKU 的 size 为所有尺寸列表
            new_attrs = copy.deepcopy(primary.attributes)
            # 找到 size 使用的键名
            size_key = next((k for k in SIZE_KEYS if k in new_attrs), SIZE_KEYS[0])
            new_attrs[size_key] = all_sizes
            primary.attributes = new_attrs
            session.add(primary)

            # 将其余 SKU 标记为 superseded
            for other in others:
                other.superseded = True
                session.add(other)

        merge_count += 1
        superseded_count += len(others)

    if not dry_run:
        await session.commit()
        print(
            f"\n[DONE] 已提交：合并组 {merge_count} 个，废弃 SKU {superseded_count} 个"
        )

        # ── 同步 Page.sku_count 和 PDFJob.total_skus ──────────────────────
        print("[INFO] 同步 sku_count 计数器...")
        result = await session.execute(
            select(Page).where(Page.job_id == job_id)
        )
        pages = result.scalars().all()
        for page in pages:
            r = await session.execute(
                select(func.count()).where(
                    SKU.job_id == job_id,
                    SKU.page_number == page.page_number,
                    SKU.superseded.is_(False),
                )
            )
            real = r.scalar()
            if page.sku_count != real:
                page.sku_count = real
                session.add(page)

        r = await session.execute(
            select(func.count()).where(
                SKU.job_id == job_id, SKU.superseded.is_(False)
            )
        )
        real_total = r.scalar()
        result = await session.execute(
            select(PDFJob).where(PDFJob.job_id == job_id)
        )
        job_obj = result.scalar_one_or_none()
        if job_obj and job_obj.total_skus != real_total:
            job_obj.total_skus = real_total
            session.add(job_obj)

        await session.commit()
        print(f"[INFO] total_skus 更新为 {real_total}")
    else:
        print(
            f"\n[DRY-RUN] 将合并组 {merge_count} 个，废弃 SKU {superseded_count} 个（未修改数据库）"
        )


async def main() -> None:
    parser = argparse.ArgumentParser(description="合并同商品不同规格 SKU")
    parser.add_argument("job_id", help="要处理的 PDF job UUID")
    parser.add_argument(
        "--dry-run", action="store_true", help="只打印计划，不修改数据库"
    )
    args = parser.parse_args()

    engine, session_factory = init_db(DB_URL)
    async with session_factory() as session:
        await merge_skus_for_job(args.job_id, args.dry_run, session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
