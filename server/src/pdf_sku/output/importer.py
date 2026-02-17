"""
增量导入器。对齐: Output 详设 §4.1

- 每页完成 → 增量导入 valid SKU
- [C3] import_dedup 幂等保护
- [P1-O1] Upsert 语义 (跨页修正)
- [P1-O2] 背压检查
- [P1-O10] asyncio.create_task 异常回调
"""
from __future__ import annotations
import asyncio
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import ImportDedup, Page
from pdf_sku.common.enums import PageStatus
from pdf_sku.output.import_adapter import ImportAdapter, ImportResult, ImportDataError
from pdf_sku.output.backpressure import BackpressureMonitor
from pdf_sku.pipeline.ir import PageResult, SKUResult
import structlog

logger = structlog.get_logger()


class IncrementalImporter:
    def __init__(
        self,
        adapter: ImportAdapter | None = None,
        backpressure: BackpressureMonitor | None = None,
    ):
        self._adapter = adapter or ImportAdapter()
        self._bp = backpressure or BackpressureMonitor()

    async def import_page_incremental(
        self,
        db: AsyncSession,
        job_id: str,
        page_number: int,
        result: PageResult,
        attempt_no: int = 1,
    ) -> bool:
        """
        增量导入单页 SKU。

        [C3] 幂等保护: import_dedup 去重表
        [P1-O2] 背压检查

        Returns:
            True = 导入成功, False = 跳过或失败
        """
        if result.status not in ("AI_COMPLETED",):
            return False

        valid_skus = [s for s in (result.skus or []) if s.validity == "valid"]
        if not valid_skus:
            return True  # 无 valid SKU, 视为成功

        # [P1-O2] 背压检查
        if self._bp.is_throttled(job_id):
            logger.warning("import_throttled",
                           job_id=job_id, page=page_number,
                           delay=self._bp.delay_seconds)
            await asyncio.sleep(self._bp.delay_seconds)

        success_count = 0
        for sku in valid_skus:
            # [C3] 幂等去重检查
            dedup_key = f"{job_id}:{page_number}:{sku.sku_id}:{attempt_no}"
            is_dup = await self._check_dedup(db, dedup_key)
            if is_dup:
                logger.debug("import_dedup_skip", dedup_key=dedup_key)
                success_count += 1
                continue

            try:
                payload = self._build_payload(sku, job_id, page_number)
                import_result = await self._adapter.import_sku(
                    payload, revision=attempt_no)

                # 记录去重
                await self._record_dedup(
                    db, dedup_key, UUID(job_id), page_number,
                    "CONFIRMED" if import_result.confirmed else "ASSUMED")
                success_count += 1
                self._bp.on_success(job_id)

            except ImportDataError as e:
                logger.error("import_data_error",
                             sku_id=sku.sku_id, error=str(e))
                self._bp.on_failure(job_id)
                await self._record_dedup(
                    db, dedup_key, UUID(job_id), page_number, "FAILED")

            except Exception as e:
                logger.error("import_failed",
                             sku_id=sku.sku_id, error=str(e))
                self._bp.on_failure(job_id)
                raise  # 上层重试

        # 更新 Page 状态
        if success_count == len(valid_skus):
            await db.execute(
                update(Page).where(
                    Page.job_id == UUID(job_id),
                    Page.page_number == page_number,
                ).values(import_confirmation="imported_assumed")
            )
            return True
        return False

    async def on_cross_page_correction(
        self,
        db: AsyncSession,
        job_id: str,
        corrected_attrs: dict,
    ) -> int:
        """
        [P1-O1] Upsert: 跨页属性修正 → 冲正已导入数据。
        """
        from pdf_sku.common.models import SKU

        result = await db.execute(
            select(SKU).where(
                SKU.job_id == UUID(job_id),
                SKU.validity == "valid",
            )
        )
        skus = result.scalars().all()
        upserted = 0

        for sku_orm in skus:
            attrs = sku_orm.attributes or {}
            needs_update = False
            for key, new_val in corrected_attrs.items():
                if attrs.get(key) != new_val:
                    attrs[key] = new_val
                    needs_update = True

            if needs_update:
                payload = {
                    "sku_id": sku_orm.sku_external_id,
                    "attributes": attrs,
                }
                try:
                    await self._adapter.upsert_sku(
                        payload, revision=(sku_orm.confidence or 1) + 1)
                    upserted += 1
                except Exception as e:
                    logger.error("upsert_failed",
                                 sku_id=sku_orm.sku_external_id, error=str(e))

        logger.info("cross_page_correction",
                     job_id=job_id, upserted=upserted)
        return upserted

    async def _check_dedup(self, db: AsyncSession, dedup_key: str) -> bool:
        """[C3] 检查是否已导入。"""
        result = await db.execute(
            select(ImportDedup.id).where(ImportDedup.dedup_key == dedup_key))
        return result.scalar_one_or_none() is not None

    async def _record_dedup(
        self,
        db: AsyncSession,
        dedup_key: str,
        job_id: UUID,
        page_number: int,
        status: str,
    ) -> None:
        """记录去重。"""
        db.add(ImportDedup(
            dedup_key=dedup_key,
            job_id=job_id,
            page_number=page_number,
            import_status=status,
        ))

    @staticmethod
    def _build_payload(sku: SKUResult, job_id: str, page_number: int) -> dict:
        return {
            "sku_id": sku.sku_id,
            "job_id": job_id,
            "page_number": page_number,
            "attributes": sku.attributes,
            "confidence": sku.confidence,
            "extraction_method": sku.extraction_method,
        }
