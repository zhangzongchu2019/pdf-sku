"""Auth 路由 — 注册 / 登录 / 查看个人信息 / 管理员创建用户。"""
from __future__ import annotations
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.dependencies import DBSession
from pdf_sku.common.models import User, AnnotatorProfile
from pdf_sku.auth.security import hash_password, verify_password, create_access_token
from pdf_sku.auth.dependencies import CurrentUser, AdminUser

router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


# ── Schemas ──

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field("", max_length=128)
    role: str = Field("uploader", pattern="^(uploader|annotator)$")
    merchant_id: str | None = None
    specialties: list[str] | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field("", max_length=128)
    role: str = Field("annotator", pattern="^(uploader|annotator|admin)$")
    merchant_id: str | None = None
    specialties: list[str] | None = None


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(None, max_length=128)
    merchant_id: str | None = None
    specialties: list[str] | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=6, max_length=128)


class AdminUpdateUserRequest(BaseModel):
    display_name: str | None = None
    role: str | None = Field(None, pattern="^(uploader|annotator|admin)$")
    merchant_id: str | None = None
    specialties: list[str] | None = None
    reset_password: str | None = Field(None, min_length=6, max_length=128)


# ── 注册 (自助, 只允许 uploader / annotator) ──

@router.post("/register", status_code=201)
async def register(db: DBSession, body: RegisterRequest):
    # 检查用户名唯一
    existing = await db.execute(
        select(func.count()).select_from(User).where(User.username == body.username)
    )
    if existing.scalar():
        raise HTTPException(409, "用户名已存在")

    user = User(
        username=body.username,
        display_name=body.display_name or body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        merchant_id=body.merchant_id,
        specialties=body.specialties,
    )
    db.add(user)
    await db.flush()  # 先 flush 以获取 user_id (UUID)

    # 如果是 annotator, 同步创建 AnnotatorProfile
    if body.role == "annotator":
        profile = AnnotatorProfile(
            annotator_id=str(user.user_id),
            specialties=body.specialties,
        )
        db.add(profile)
        await db.flush()

    token = create_access_token({"sub": str(user.user_id), "role": user.role})
    return {
        "user_id": str(user.user_id),
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "token": token,
    }


# ── 登录 ──

@router.post("/login")
async def login(db: DBSession, body: LoginRequest):
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(401, "用户名或密码错误")
    if not user.is_active:
        raise HTTPException(403, "账号已被禁用")

    # 更新最后登录时间
    user.last_login_at = datetime.now(timezone.utc)

    token = create_access_token({"sub": str(user.user_id), "role": user.role})
    return {
        "user_id": str(user.user_id),
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "merchant_id": user.merchant_id,
        "token": token,
    }


# ── 查看当前用户 ──

@router.get("/me")
async def get_me(user: CurrentUser):
    return {
        "user_id": str(user.user_id),
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "merchant_id": user.merchant_id,
        "specialties": user.specialties,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


# ── 管理员创建用户 (可创建任何角色) ──

@router.post("/users", status_code=201)
async def admin_create_user(db: DBSession, body: CreateUserRequest, _admin: AdminUser = ...):
    existing = await db.execute(
        select(func.count()).select_from(User).where(User.username == body.username)
    )
    if existing.scalar():
        raise HTTPException(409, "用户名已存在")

    user = User(
        username=body.username,
        display_name=body.display_name or body.username,
        password_hash=hash_password(body.password),
        role=body.role,
        merchant_id=body.merchant_id,
        specialties=body.specialties,
    )
    db.add(user)
    await db.flush()  # 先 flush 以获取 user_id (UUID)

    if body.role == "annotator":
        profile = AnnotatorProfile(
            annotator_id=str(user.user_id),
            specialties=body.specialties,
        )
        db.add(profile)
        await db.flush()

    return {
        "user_id": str(user.user_id),
        "username": user.username,
        "role": user.role,
        "display_name": user.display_name,
    }


# ── 管理员: 列出所有用户 ──

@router.get("/users")
async def list_users(db: DBSession, _admin: AdminUser = ...):
    result = await db.execute(
        select(User).order_by(User.created_at.desc())
    )
    users = result.scalars().all()
    return {"data": [
        {
            "user_id": str(u.user_id),
            "username": u.username,
            "display_name": u.display_name,
            "role": u.role,
            "is_active": u.is_active,
            "merchant_id": u.merchant_id,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
        }
        for u in users
    ]}


# ── 管理员: 禁用/启用用户 ──

@router.patch("/users/{user_id}/status")
async def toggle_user_status(
    db: DBSession,
    user_id: str,
    is_active: bool = Body(..., embed=True),
    _admin: AdminUser = ...,
):
    from uuid import UUID
    result = await db.execute(select(User).where(User.user_id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    user.is_active = is_active
    return {"ok": True, "user_id": str(user.user_id), "is_active": user.is_active}


# ── 修改个人信息 ──

@router.patch("/me")
async def update_profile(db: DBSession, body: UpdateProfileRequest, user: CurrentUser):
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.merchant_id is not None:
        user.merchant_id = body.merchant_id
    if body.specialties is not None:
        user.specialties = body.specialties
    return {
        "user_id": str(user.user_id),
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "merchant_id": user.merchant_id,
        "specialties": user.specialties,
    }


# ── 修改密码 ──

@router.post("/me/change-password")
async def change_password(db: DBSession, body: ChangePasswordRequest, user: CurrentUser):
    if not verify_password(body.old_password, user.password_hash):
        raise HTTPException(400, "原密码不正确")
    user.password_hash = hash_password(body.new_password)
    return {"ok": True, "message": "密码已更新"}


# ── 管理员: 修改用户信息 / 重置密码 ──

@router.patch("/users/{user_id}")
async def admin_update_user(
    db: DBSession,
    user_id: str,
    body: AdminUpdateUserRequest,
    _admin: AdminUser = ...,
):
    from uuid import UUID
    result = await db.execute(select(User).where(User.user_id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "用户不存在")
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.role is not None:
        user.role = body.role
    if body.merchant_id is not None:
        user.merchant_id = body.merchant_id
    if body.specialties is not None:
        user.specialties = body.specialties
    if body.reset_password is not None:
        user.password_hash = hash_password(body.reset_password)
    return {
        "user_id": str(user.user_id),
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "is_active": user.is_active,
        "merchant_id": user.merchant_id,
    }
