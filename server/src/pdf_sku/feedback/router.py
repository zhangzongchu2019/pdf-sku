"""Feedback 路由。对齐: OpenAPI + Feedback 详设"""
from __future__ import annotations
from uuid import UUID

from fastapi import APIRouter, Path, Body, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.dependencies import DBSession
from pdf_sku.common.models import (
    CalibrationRecord, EvalReport, AnnotationExample, CustomAttrUpgrade,
)
from pdf_sku.feedback.calibration_engine import CalibrationEngine
from pdf_sku.feedback.golden_set_eval import GoldenSetEvaluator
from pdf_sku.feedback.fewshot_sync import FewShotSyncer

router = APIRouter(prefix="/api/v1", tags=["Feedback"])

_calibration = CalibrationEngine()
_evaluator = GoldenSetEvaluator()
_fewshot = FewShotSyncer()


# === Calibration ===

@router.get("/calibrations")
async def list_calibrations(
    db: DBSession,
    status: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    """校准记录列表。"""
    query = select(CalibrationRecord).order_by(CalibrationRecord.created_at.desc())
    if status:
        query = query.where(CalibrationRecord.status == status)
    query = query.offset((page - 1) * size).limit(size)
    result = await db.execute(query)
    records = result.scalars().all()
    return {"data": [_calib_to_dict(r) for r in records]}


@router.get("/calibrations/{calibration_id}")
async def get_calibration(db: DBSession, calibration_id: str = Path(...)):
    result = await db.execute(
        select(CalibrationRecord).where(
            CalibrationRecord.calibration_id == calibration_id))
    record = result.scalar_one_or_none()
    if not record:
        raise HTTPException(404, "Calibration not found")
    return _calib_to_dict(record)


@router.post("/calibrations/{calibration_id}/approve")
async def approve_calibration(
    db: DBSession,
    calibration_id: str = Path(...),
    operator: str = Body("ops", embed=True),
):
    ok = await _calibration.apply_calibration(db, calibration_id, operator)
    if not ok:
        raise HTTPException(400, "Cannot approve (not PENDING or not found)")
    await db.commit()
    return {"status": "approved"}


@router.post("/calibrations/{calibration_id}/reject")
async def reject_calibration(
    db: DBSession,
    calibration_id: str = Path(...),
    reason: str = Body("", embed=True),
    operator: str = Body("ops", embed=True),
):
    ok = await _calibration.reject_calibration(db, calibration_id, reason, operator)
    if not ok:
        raise HTTPException(400, "Cannot reject")
    await db.commit()
    return {"status": "rejected"}


@router.post("/calibrations/trigger")
async def trigger_calibration(db: DBSession):
    """手动触发校准。"""
    record = await _calibration.check_and_calibrate(db)
    await db.commit()
    if record:
        return {"status": "created", "calibration_id": str(record.calibration_id)}
    return {"status": "skipped", "message": "No calibration needed"}


# === Golden Set Eval ===

@router.post("/eval/golden-set")
async def run_golden_set_eval(db: DBSession, body: dict = Body(...)):
    """运行 Golden Set 评测。"""
    report = await _evaluator.evaluate(
        db,
        golden_set_id=body.get("golden_set_id", "default"),
        config_version=body.get("config_version", "v1"),
        predictions=body.get("predictions", []),
        ground_truth=body.get("ground_truth", []),
    )
    await db.commit()
    return _report_to_dict(report)


@router.get("/eval/reports")
async def list_eval_reports(
    db: DBSession,
    golden_set_id: str | None = None,
    limit: int = Query(20, ge=1, le=100),
):
    reports = await _evaluator.get_reports(db, golden_set_id, limit)
    return {"data": [_report_to_dict(r) for r in reports]}


# === Few-Shot ===

@router.get("/fewshot/examples")
async def list_fewshot_examples(
    db: DBSession,
    task_type: str = Query(...),
    category: str | None = None,
    limit: int = Query(5, ge=1, le=50),
):
    examples = await _fewshot.get_examples(db, task_type, category, limit)
    return {"data": [
        {
            "id": e.id,
            "task_type": e.task_type,
            "category": e.category,
            "output_json": e.output_json,
            "quality_score": e.quality_score,
            "is_confirmed": e.is_confirmed,
        }
        for e in examples
    ]}


# === Attr Upgrades ===

@router.get("/ops/custom-attr-upgrades")
async def list_upgrades(db: DBSession, status: str | None = None):
    query = select(CustomAttrUpgrade)
    result = await db.execute(query)
    upgrades = result.scalars().all()
    return {"data": [
        {
            "upgrade_id": str(u.upgrade_id),
            "attr_name": u.attr_name,
            "category": u.category,
            "suggested_type": u.suggested_type,
            "source_feedback_count": u.source_feedback_count,
        }
        for u in upgrades
    ]}


@router.post("/ops/custom-attr-upgrades/{upgrade_id}/review")
async def review_upgrade(
    db: DBSession,
    upgrade_id: str = Path(...),
    body: dict = Body(...),
):
    return {"status": "reviewed"}


# === Helpers ===

def _calib_to_dict(r: CalibrationRecord) -> dict:
    return {
        "calibration_id": str(r.calibration_id),
        "profile_id": r.profile_id,
        "type": r.type,
        "sample_count": r.sample_count,
        "suggested_adjustments": r.suggested_adjustments,
        "status": r.status,
        "applied": r.applied,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _report_to_dict(r: EvalReport) -> dict:
    return {
        "id": r.id,
        "golden_set_id": r.golden_set_id,
        "config_version": r.config_version,
        "sku_precision": r.sku_precision,
        "sku_recall": r.sku_recall,
        "sku_f1": r.sku_f1,
        "binding_accuracy": r.binding_accuracy,
        "human_intervention_rate": r.human_intervention_rate,
        "report_data": r.report_data,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }
