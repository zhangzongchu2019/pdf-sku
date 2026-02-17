"""
SKU 导出 + ID 生成。对齐: Pipeline 详设 §5.2 Phase 9

SKU ID 格式: {hash_prefix}_{page_no}_{seq}
[C12] 坐标归一化后按 bbox_y1 主排序, bbox_x1 次排序
"""
from __future__ import annotations
from pdf_sku.pipeline.ir import SKUResult, PageResult
import structlog

logger = structlog.get_logger()


class SKUIdGenerator:
    """SKU ID 生成器 (坐标排序)。"""

    def assign_ids(
        self,
        skus: list[SKUResult],
        hash_prefix: str,
        page_no: int,
        page_height: float = 1.0,
    ) -> list[SKUResult]:
        """
        [C12] 按归一化坐标排序 + 分配 ID。
        主排序: bbox_y1 (纵向), 次排序: bbox_x1 (横向)
        """
        page_h = max(1.0, page_height)

        def sort_key(s: SKUResult):
            y = s.source_bbox[1] / page_h if len(s.source_bbox) >= 4 else 0
            x = s.source_bbox[0] / page_h if len(s.source_bbox) >= 4 else 0
            return (round(y, 2), round(x, 2))

        skus.sort(key=sort_key)
        for i, sku in enumerate(skus, 1):
            sku.sku_id = f"{hash_prefix}_{page_no:03d}_{i:03d}"
        return skus


class SKUExporter:
    """导出 SKU 到标准格式。"""

    async def export(
        self,
        skus: list[SKUResult],
        job_id: str,
        page_no: int,
        profile: dict | None = None,
    ) -> list[dict]:
        """导出 valid SKU 为下游消费格式。"""
        exported = []
        for sku in skus:
            if sku.validity == "valid":
                exported.append({
                    "sku_id": sku.sku_id,
                    "job_id": job_id,
                    "page_no": page_no,
                    "attributes": sku.attributes,
                    "confidence": sku.confidence,
                    "extraction_method": sku.extraction_method,
                })
        logger.info("sku_exported",
                     job_id=job_id, page_no=page_no,
                     total=len(skus), exported=len(exported))
        return exported
