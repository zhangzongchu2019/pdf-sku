"""
Golden Set 离线评测。对齐: Feedback 详设 + 质量指标体系

- SKU F1 (precision, recall)
- Binding accuracy
- Human intervention rate
- Config 版本 × Golden Set → EvalReport
"""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import EvalReport
import structlog

logger = structlog.get_logger()


class GoldenSetEvaluator:
    """Golden Set 离线评测器。"""

    async def evaluate(
        self,
        db: AsyncSession,
        golden_set_id: str,
        config_version: str,
        predictions: list[dict],
        ground_truth: list[dict],
    ) -> EvalReport:
        """
        对比 AI 预测 vs 人工标注 Ground Truth。

        predictions: [{"page": 1, "skus": [...], "bindings": [...]}]
        ground_truth: [{"page": 1, "skus": [...], "bindings": [...]}]
        """
        # SKU 指标
        sku_metrics = self._compute_sku_metrics(predictions, ground_truth)

        # Binding 指标
        binding_acc = self._compute_binding_accuracy(predictions, ground_truth)

        # Human intervention rate
        human_rate = self._compute_human_rate(predictions)

        report = EvalReport(
            golden_set_id=golden_set_id,
            config_version=config_version,
            sku_precision=sku_metrics["precision"],
            sku_recall=sku_metrics["recall"],
            sku_f1=sku_metrics["f1"],
            binding_accuracy=binding_acc,
            human_intervention_rate=human_rate,
            report_data={
                "sku_metrics": sku_metrics,
                "binding_accuracy": binding_acc,
                "human_intervention_rate": human_rate,
                "page_count": len(predictions),
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        db.add(report)

        logger.info("golden_set_evaluated",
                     golden_set_id=golden_set_id,
                     config_version=config_version,
                     f1=sku_metrics["f1"],
                     binding_acc=binding_acc)
        return report

    async def get_reports(
        self, db: AsyncSession,
        golden_set_id: str | None = None,
        limit: int = 20,
    ) -> list[EvalReport]:
        query = select(EvalReport).order_by(EvalReport.created_at.desc()).limit(limit)
        if golden_set_id:
            query = query.where(EvalReport.golden_set_id == golden_set_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def _compute_sku_metrics(
        predictions: list[dict], ground_truth: list[dict],
    ) -> dict:
        """SKU-level precision / recall / F1。"""
        tp = fp = fn = 0

        gt_map = {g["page"]: set(
            s.get("model_number", s.get("product_name", ""))
            for s in g.get("skus", [])
        ) for g in ground_truth}

        for pred in predictions:
            page = pred["page"]
            pred_skus = set(
                s.get("model_number", s.get("product_name", ""))
                for s in pred.get("skus", [])
            )
            gt_skus = gt_map.get(page, set())

            # 清理空值
            pred_skus.discard("")
            gt_skus.discard("")

            tp += len(pred_skus & gt_skus)
            fp += len(pred_skus - gt_skus)
            fn += len(gt_skus - pred_skus)

        precision = tp / max(1, tp + fp)
        recall = tp / max(1, tp + fn)
        f1 = 2 * precision * recall / max(0.001, precision + recall)

        return {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn,
        }

    @staticmethod
    def _compute_binding_accuracy(
        predictions: list[dict], ground_truth: list[dict],
    ) -> float:
        """绑定准确率。"""
        correct = total = 0
        gt_map = {}
        for g in ground_truth:
            for b in g.get("bindings", []):
                gt_map[(g["page"], b.get("sku_id"))] = b.get("image_id")

        for pred in predictions:
            for b in pred.get("bindings", []):
                key = (pred["page"], b.get("sku_id"))
                total += 1
                if gt_map.get(key) == b.get("image_id"):
                    correct += 1

        return round(correct / max(1, total), 4)

    @staticmethod
    def _compute_human_rate(predictions: list[dict]) -> float:
        """人工干预率 (needs_review 比例)。"""
        total = len(predictions)
        if total == 0:
            return 0.0
        human = sum(1 for p in predictions if p.get("needs_review"))
        return round(human / total, 4)
