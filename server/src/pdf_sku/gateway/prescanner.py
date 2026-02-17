"""规则预筛。对齐: Gateway 详设 §5.4"""
from __future__ import annotations
from dataclasses import dataclass, field
import fitz  # PyMuPDF
import structlog

logger = structlog.get_logger()


@dataclass
class PrescanRuleConfig:
    min_text_chars_for_blank: int = 10
    min_ocr_rate: float = 0.3
    min_image_ratio: float = 0.1
    blank_rate_penalty_weight: float = 0.15
    low_ocr_penalty_weight: float = 0.20
    low_image_penalty_weight: float = 0.10

    @classmethod
    def from_dict(cls, d: dict) -> PrescanRuleConfig:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class PrescanPenalty:
    rule: str
    actual_value: float
    threshold: float
    weight: float


@dataclass
class PrescanResult:
    all_blank: bool = False
    blank_pages: list[int] = field(default_factory=list)
    penalties: list[PrescanPenalty] = field(default_factory=list)
    total_penalty: float = 0.0
    raw_metrics: dict = field(default_factory=dict)


class Prescanner:
    async def scan(self, file_path: str, rules: PrescanRuleConfig | None = None) -> PrescanResult:
        if rules is None:
            rules = PrescanRuleConfig()

        with fitz.open(file_path) as doc:
            total = doc.page_count

            # 1. 空白页检测
            blank_pages = self._detect_blank_pages(doc, rules.min_text_chars_for_blank)
            all_blank = len(blank_pages) == total and total > 0

            # 2. OCR率 (非空白页的文本覆盖度)
            non_blank_indices = [i for i in range(total) if (i + 1) not in blank_pages]
            ocr_rate = self._compute_ocr_rate(doc, non_blank_indices) if non_blank_indices else 0.0

            # 3. 图片数
            image_count = self._count_images(doc, non_blank_indices) if non_blank_indices else 0

        blank_rate = len(blank_pages) / total if total > 0 else 1.0
        raw_metrics = {
            "total_pages": total,
            "blank_page_count": len(blank_pages),
            "blank_rate": round(blank_rate, 4),
            "ocr_rate": round(ocr_rate, 4),
            "image_count": image_count,
        }

        # 4. 计算扣分
        penalties = self._apply_penalties(raw_metrics, rules)
        total_penalty = sum(p.weight for p in penalties)

        result = PrescanResult(
            all_blank=all_blank,
            blank_pages=blank_pages,
            penalties=penalties,
            total_penalty=round(total_penalty, 4),
            raw_metrics=raw_metrics,
        )
        logger.info("prescan_complete",
                     total_pages=total, blank_count=len(blank_pages),
                     ocr_rate=round(ocr_rate, 3), images=image_count,
                     all_blank=all_blank, penalty=round(total_penalty, 3))
        return result

    def _detect_blank_pages(self, doc: fitz.Document, min_chars: int) -> list[int]:
        blank = []
        for i in range(doc.page_count):
            page = doc[i]
            text = page.get_text("text").strip()
            images = page.get_images()
            if len(text) < min_chars and len(images) == 0:
                blank.append(i + 1)  # 1-indexed
        return blank

    def _compute_ocr_rate(self, doc: fitz.Document, page_indices: list[int]) -> float:
        if not page_indices:
            return 0.0
        has_text_count = 0
        for i in page_indices:
            page = doc[i]
            text = page.get_text("text").strip()
            if len(text) > 20:
                has_text_count += 1
        return has_text_count / len(page_indices)

    def _count_images(self, doc: fitz.Document, page_indices: list[int]) -> int:
        total_images = 0
        seen_xrefs: set[int] = set()
        for i in page_indices:
            page = doc[i]
            for img in page.get_images():
                xref = img[0]
                if xref not in seen_xrefs:
                    seen_xrefs.add(xref)
                    total_images += 1
        return total_images

    def _apply_penalties(self, metrics: dict, rules: PrescanRuleConfig) -> list[PrescanPenalty]:
        penalties = []
        blank_rate = metrics["blank_rate"]
        ocr_rate = metrics["ocr_rate"]
        total_pages = metrics["total_pages"]
        image_count = metrics["image_count"]

        # 高空白率扣分
        if blank_rate > 0.5:
            penalties.append(PrescanPenalty(
                rule="high_blank_rate", actual_value=blank_rate,
                threshold=0.5, weight=rules.blank_rate_penalty_weight,
            ))

        # 低OCR率扣分
        if ocr_rate < rules.min_ocr_rate and total_pages > 0:
            penalties.append(PrescanPenalty(
                rule="low_ocr_rate", actual_value=ocr_rate,
                threshold=rules.min_ocr_rate, weight=rules.low_ocr_penalty_weight,
            ))

        # 低图片率扣分
        non_blank_count = total_pages - metrics["blank_page_count"]
        if non_blank_count > 0:
            image_ratio = image_count / non_blank_count
            if image_ratio < rules.min_image_ratio:
                penalties.append(PrescanPenalty(
                    rule="low_image_ratio", actual_value=round(image_ratio, 4),
                    threshold=rules.min_image_ratio, weight=rules.low_image_penalty_weight,
                ))

        return penalties
