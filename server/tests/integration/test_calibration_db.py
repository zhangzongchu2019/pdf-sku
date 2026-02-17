"""CalibrationEngine DB 集成测试。"""
import pytest
from uuid import uuid4
from datetime import datetime, timezone
from pdf_sku.common.models import CalibrationRecord
from pdf_sku.feedback.calibration_engine import CalibrationEngine


@pytest.mark.asyncio
async def test_calibration_skip_few_samples(db):
    assert await CalibrationEngine().check_and_calibrate(db) is None


@pytest.mark.asyncio
async def test_calibration_approval_flow(db):
    cid = uuid4()
    db.add(CalibrationRecord(
        calibration_id=cid, profile_id="default", type="THRESHOLD",
        period_start=datetime.now(timezone.utc), period_end=datetime.now(timezone.utc),
        sample_count=100, suggested_adjustments={"suggestions": [{"action": "test"}]}, status="PENDING"))
    await db.flush()
    assert await CalibrationEngine().apply_calibration(db, str(cid), "ops") is True


@pytest.mark.asyncio
async def test_calibration_reject(db):
    cid = uuid4()
    db.add(CalibrationRecord(
        calibration_id=cid, profile_id="default", type="THRESHOLD",
        period_start=datetime.now(timezone.utc), period_end=datetime.now(timezone.utc),
        sample_count=50, suggested_adjustments={}, status="PENDING"))
    await db.flush()
    assert await CalibrationEngine().reject_calibration(db, str(cid), "bad", "ops") is True
