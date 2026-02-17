"""Config API 路由。对齐: OpenAPI V2.0 §/config"""
from __future__ import annotations
from fastapi import APIRouter, Query, Path, Body
from fastapi.responses import JSONResponse
from pdf_sku.common.dependencies import DBSession
from pdf_sku.config.service import ConfigProvider

router = APIRouter(prefix="/api/v1/config", tags=["Config"])
_provider = ConfigProvider()


@router.get("/profiles")
async def list_profiles(db: DBSession):
    profiles = await _provider.list_profiles(db)
    return {"data": profiles}


@router.get("/profiles/{profile_id}")
async def get_profile(profile_id: str, db: DBSession):
    profile = await _provider.get_active_profile(db, profile_id)
    return profile


@router.get("/profiles/{profile_id}/history")
async def get_profile_history(
    profile_id: str, db: DBSession,
    limit: int = Query(20, ge=1, le=100),
):
    history = await _provider.get_profile_history(db, profile_id, limit)
    return {"data": history}


@router.put("/profiles/{profile_id}")
async def update_profile(
    profile_id: str, db: DBSession, body: dict,
):
    """
    更新配置 (乐观锁)。
    Body: {"thresholds": {...}, "confidence_weights": {...}, "expected_version": "v1.0", ...}
    """
    result = await _provider.create_or_update_profile(
        db=db,
        profile_id=profile_id,
        data=body,
        expected_version=body.get("expected_version"),
        created_by=body.get("created_by", ""),
        change_reason=body.get("change_reason", ""),
    )
    await db.commit()
    return result


@router.post("/profiles")
async def create_profile(db: DBSession, body: dict):
    """创建新 profile。"""
    profile_id = body.pop("profile_id", "custom")
    result = await _provider.create_or_update_profile(
        db=db,
        profile_id=profile_id,
        data=body,
        created_by=body.get("created_by", ""),
        change_reason=body.get("change_reason", "API created"),
    )
    await db.commit()
    return result


@router.post("/profiles/{profile_id}/impact-preview")
async def impact_preview(
    db: DBSession,
    profile_id: str = Path(...),
    body: dict = Body(...),
):
    """阈值变更影响预估。"""
    from pdf_sku.config.impact_preview import ImpactPreviewCalculator
    calculator = ImpactPreviewCalculator()
    result = await calculator.preview(
        db,
        current_thresholds=body.get("current", {"A": 0.85, "B": 0.45}),
        proposed_thresholds=body.get("proposed", {}),
    )
    return result.to_dict()
