"""
采样器。对齐: Evaluator 详设 §5.3

策略:
- ≤40 页: 全量 (排除空白页)
- >40 页: 特征加权分层采样 (高/中/低复杂度)
- 目录页过滤 (TOC_KEYWORDS)
- 首尾各 2 页必选
"""
from __future__ import annotations
import random
import structlog

logger = structlog.get_logger()

TOC_KEYWORDS = {"目录", "contents", "table of contents", "index", "catalogue"}


class Sampler:
    FULL_THRESHOLD = 40

    def select_pages(
        self,
        total: int,
        blank_pages: list[int] | None = None,
        threshold: int | None = None,
        page_features: dict | None = None,
    ) -> list[int]:
        """
        选取评估用采样页。

        Args:
            total: 总页数
            blank_pages: 空白页列表 (1-indexed)
            threshold: 全量采样阈值 (默认40)
            page_features: {page_no: {"image_count": int, "ocr_rate": float, "text_hint": str}}
        Returns:
            采样页列表 (1-indexed, sorted)
        """
        threshold = threshold or self.FULL_THRESHOLD
        blank_set = set(blank_pages or [])
        effective = [p for p in range(1, total + 1) if p not in blank_set]

        if not effective:
            return []

        # 过滤目录页
        if page_features:
            before = len(effective)
            effective = [p for p in effective if not self._is_toc_page(p, page_features)]
            filtered = before - len(effective)
            if filtered:
                logger.debug("toc_pages_filtered", count=filtered)

        if not effective:
            return []

        if len(effective) <= threshold:
            return effective

        # 特征加权采样
        if page_features:
            return self._feature_weighted_sample(effective, page_features, threshold)

        # Fallback: 分层抽样
        return self._stratified_sample(effective, threshold)

    def _feature_weighted_sample(
        self, effective: list[int], page_features: dict, sample_size: int
    ) -> list[int]:
        """按复杂度分层: 高(权重3) / 中(权重2) / 低(权重1)。"""
        head = effective[:2]
        tail = effective[-2:]
        must_select = set(head + tail)
        middle = [p for p in effective if p not in must_select]

        high, med, low = [], [], []
        for p in middle:
            feat = page_features.get(p, {})
            img = feat.get("image_count", 0)
            ocr = feat.get("ocr_rate", 1.0)
            if img > 5 or ocr < 0.5:
                high.append(p)
            elif img > 2 or ocr < 0.8:
                med.append(p)
            else:
                low.append(p)

        remaining = sample_size - len(must_select)
        if remaining <= 0:
            return sorted(must_select)[:sample_size]

        total_weight = len(high) * 3 + len(med) * 2 + len(low) * 1
        if total_weight == 0:
            return sorted(must_select)

        def pick(pool: list[int], weight: int) -> list[int]:
            if not pool or total_weight == 0:
                return []
            n = max(1, round(remaining * len(pool) * weight / total_weight))
            return random.sample(pool, min(n, len(pool)))

        selected = set(must_select)
        selected.update(pick(high, 3))
        selected.update(pick(med, 2))
        selected.update(pick(low, 1))

        result = sorted(selected)[:sample_size]
        logger.info("sampler_result",
                     total=len(effective), sampled=len(result),
                     high=len(high), med=len(med), low=len(low))
        return result

    def _stratified_sample(self, effective: list[int], sample_size: int) -> list[int]:
        """分层抽样: 首尾各 2 页 + 中间均匀。"""
        head = effective[:2]
        tail = effective[-2:]
        middle_pool = effective[2:-2]
        remaining = sample_size - len(head) - len(tail)
        middle = []
        if remaining > 0 and middle_pool:
            step = max(1, len(middle_pool) // remaining)
            middle = middle_pool[::step][:remaining]
        return sorted(set(head + middle + tail))

    @staticmethod
    def _is_toc_page(page_no: int, page_features: dict) -> bool:
        feat = page_features.get(page_no, {})
        text_hint = feat.get("text_hint", "").lower()
        return (feat.get("image_count", 0) == 0 and
                any(kw in text_hint for kw in TOC_KEYWORDS))
