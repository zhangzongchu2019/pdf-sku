#!/usr/bin/env python3
"""
批量为现有任务生成缩略图缓存。

用法:
    source ~/envs/pdf/bin/activate
    python server/scripts/generate_thumbnails.py [--jobs-dir /data/jobs] [--workers 4]

生成内容:
    - images/.cache/{image_id}_thumb.jpg   (128px, q70)
    - images/.cache/{image_id}_medium.jpg  (800px, q80)
    - screenshots/.cache/page-{n}_thumb.jpg
    - screenshots/.cache/page-{n}_medium.jpg
"""
import argparse
import sys
import time
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed

from PIL import Image as PILImage

PILImage.MAX_IMAGE_PIXELS = 300_000_000  # 允许大尺寸 PDF 渲染图

SIZES = {
    "thumb": (128, 70),
    "medium": (800, 80),
}


def generate_thumbnail(src: Path, cache_dir: Path, name: str, max_edge: int, quality: int) -> bool:
    """生成单张缩略图。返回 True 表示新生成，False 表示跳过。"""
    cache_path = cache_dir / f"{name}.jpg"
    if cache_path.exists():
        return False
    try:
        with PILImage.open(src) as im:
            if max(im.size) <= max_edge:
                return False  # 原图已足够小
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.thumbnail((max_edge, max_edge), PILImage.LANCZOS)
            cache_dir.mkdir(parents=True, exist_ok=True)
            im.save(cache_path, "JPEG", quality=quality)
        return True
    except Exception as e:
        print(f"  [WARN] {src.name} → {name}: {e}", file=sys.stderr)
        return False


def process_job(job_dir: Path) -> dict:
    """处理单个任务目录，返回统计信息。"""
    stats = {"images_generated": 0, "images_skipped": 0,
             "screenshots_generated": 0, "screenshots_skipped": 0}

    # 1. 图片缩略图
    img_dir = job_dir / "images"
    if img_dir.exists():
        cache_dir = img_dir / ".cache"
        for src in sorted(img_dir.glob("*.jpg")):
            image_id = src.stem
            for size_name, (max_edge, quality) in SIZES.items():
                name = f"{image_id}_{size_name}"
                if generate_thumbnail(src, cache_dir, name, max_edge, quality):
                    stats["images_generated"] += 1
                else:
                    stats["images_skipped"] += 1

    # 2. 截图缩略图
    ss_dir = job_dir / "screenshots"
    if ss_dir.exists():
        cache_dir = ss_dir / ".cache"
        for src in sorted(ss_dir.glob("page-*.png")):
            # page-3.png → page-3
            page_stem = src.stem
            for size_name, (max_edge, quality) in SIZES.items():
                name = f"{page_stem}_{size_name}"
                if generate_thumbnail(src, cache_dir, name, max_edge, quality):
                    stats["screenshots_generated"] += 1
                else:
                    stats["screenshots_skipped"] += 1

    return stats


def main():
    parser = argparse.ArgumentParser(description="批量生成现有任务的缩略图缓存")
    parser.add_argument("--jobs-dir", default="/data/jobs", help="任务数据根目录")
    parser.add_argument("--workers", type=int, default=4, help="并行进程数")
    args = parser.parse_args()

    jobs_root = Path(args.jobs_dir)
    job_dirs = sorted([d for d in jobs_root.iterdir() if d.is_dir()])
    print(f"找到 {len(job_dirs)} 个任务目录，使用 {args.workers} 个进程\n")

    t0 = time.time()
    totals = {"images_generated": 0, "images_skipped": 0,
              "screenshots_generated": 0, "screenshots_skipped": 0}

    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_job, d): d.name for d in job_dirs}
        for i, future in enumerate(as_completed(futures), 1):
            job_id = futures[future]
            try:
                stats = future.result()
                for k in totals:
                    totals[k] += stats[k]
                gen = stats["images_generated"] + stats["screenshots_generated"]
                if gen > 0:
                    print(f"  [{i}/{len(job_dirs)}] {job_id}: "
                          f"图片 +{stats['images_generated']}, "
                          f"截图 +{stats['screenshots_generated']}")
                else:
                    print(f"  [{i}/{len(job_dirs)}] {job_id}: 全部已存在，跳过")
            except Exception as e:
                print(f"  [{i}/{len(job_dirs)}] {job_id}: ERROR {e}", file=sys.stderr)

    elapsed = time.time() - t0
    print(f"\n完成! 耗时 {elapsed:.1f}s")
    print(f"  图片缩略图: 新生成 {totals['images_generated']}, 跳过 {totals['images_skipped']}")
    print(f"  截图缩略图: 新生成 {totals['screenshots_generated']}, 跳过 {totals['screenshots_skipped']}")


if __name__ == "__main__":
    main()
