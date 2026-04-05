"""文档级弱先验构建。"""
from __future__ import annotations

from typing import Any

from pdf_sku.pipeline.ir import ParsedPageIR

from .models import DocumentHints

_DEFAULT_IGNORE_HINTS = [
    "品牌logo",
    "宣传横幅",
    "背景装饰图",
    "非商品场景装饰物",
]


def _has_text(page: ParsedPageIR) -> bool:
    if any((block.content or "").strip() for block in page.text_blocks):
        return True
    return bool((page.raw_text or "").strip())


def _infer_theme_from_sampled_pages(sampled_pages: list[ParsedPageIR]) -> list[str]:
    if not sampled_pages:
        return []

    theme_parts: list[str] = []
    sampled = [page for page in sampled_pages if page is not None]
    if not sampled:
        return theme_parts

    table_pages = sum(1 for page in sampled if page.tables)
    image_pages = sum(1 for page in sampled if page.images)
    text_pages = sum(1 for page in sampled if _has_text(page))
    avg_image_count = sum(len(page.images) for page in sampled) / len(sampled)

    if table_pages == len(sampled):
        theme_parts.append("表格价格表")
    elif image_pages == len(sampled) and text_pages == 0:
        theme_parts.append("纯图商品目录")
    elif image_pages and text_pages:
        if avg_image_count > 1.5:
            theme_parts.append("多商品图文页")
        else:
            theme_parts.append("图文商品页")
    elif text_pages:
        theme_parts.append("文本商品页")

    return theme_parts


def build_document_hints(
    *,
    category: str | None = None,
    catalog_profile: Any | None = None,
    sampled_pages: list[ParsedPageIR] | None = None,
) -> DocumentHints:
    """从运行时已有上下文构建 document_theme / ignore_hints。"""
    theme_parts: list[str] = _infer_theme_from_sampled_pages(sampled_pages or [])
    ignore_hints = list(_DEFAULT_IGNORE_HINTS)

    if category:
        theme_parts.append(str(category).strip())

    profile = catalog_profile
    if profile is not None:
        dominant = str(getattr(profile, "dominant_category", "") or "").strip()
        if dominant:
            theme_parts.append(dominant)
        else:
            main_categories = sorted(str(item) for item in getattr(profile, "main_categories", set()) if item)
            if main_categories:
                theme_parts.append("/".join(main_categories[:3]))

        if getattr(profile, "is_combo_catalog", False):
            theme_parts.append("组合套系图册")
            ignore_hints.append("套餐说明示意图")
        if getattr(profile, "is_pure_image_catalog", False):
            theme_parts.append("纯图商品目录")
        if getattr(profile, "is_one_product_per_page", False):
            theme_parts.append("每页单商品多视角目录")

        brand_names = sorted(str(item) for item in getattr(profile, "brand_names", set()) if item)
        if brand_names:
            theme_parts.append(f"品牌:{'/'.join(brand_names[:2])}")

    # 去重并保持顺序
    seen_theme: set[str] = set()
    document_theme_parts = []
    for part in theme_parts:
        if part and part not in seen_theme:
            seen_theme.add(part)
            document_theme_parts.append(part)

    seen_ignore: set[str] = set()
    deduped_ignore = []
    for hint in ignore_hints:
        if hint and hint not in seen_ignore:
            seen_ignore.add(hint)
            deduped_ignore.append(hint)

    return DocumentHints(
        document_theme=" / ".join(document_theme_parts),
        ignore_hints=deduped_ignore,
    )


def merge_document_hints(*hints: DocumentHints | None) -> DocumentHints:
    """按顺序合并多份弱提示。"""
    theme_parts: list[str] = []
    ignore_hints: list[str] = []
    for hints_item in hints:
        if not hints_item:
            continue
        if hints_item.document_theme:
            theme_parts.extend(
                part.strip()
                for part in hints_item.document_theme.split(" / ")
                if part.strip()
            )
        ignore_hints.extend(hint.strip() for hint in hints_item.ignore_hints if hint.strip())

    seen_theme: set[str] = set()
    merged_theme = []
    for part in theme_parts:
        if part not in seen_theme:
            seen_theme.add(part)
            merged_theme.append(part)

    seen_ignore: set[str] = set()
    merged_ignore = []
    for hint in ignore_hints:
        if hint not in seen_ignore:
            seen_ignore.add(hint)
            merged_ignore.append(hint)

    return DocumentHints(
        document_theme=" / ".join(merged_theme),
        ignore_hints=merged_ignore,
    )
