"""认证依赖 — 注入当前用户, 可限定角色。"""
from __future__ import annotations
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.auth.security import decode_access_token
from pdf_sku.common.dependencies import DBSession
from pdf_sku.common.models import User

_bearer = HTTPBearer(auto_error=False)


async def get_current_user(
    db: DBSession,
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    """从 Authorization: Bearer <token> 提取并校验用户。"""
    if cred is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "未登录，请先登录")
    try:
        payload = decode_access_token(cred.credentials)
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token 无效")
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token 已过期或无效")

    result = await db.execute(select(User).where(User.user_id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已禁用")
    return user


# 便捷类型别名
CurrentUser = Annotated[User, Depends(get_current_user)]


def _role_checker(*roles: str):
    """工厂：生成限定角色的依赖函数。"""
    async def _check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"需要角色 {'/'.join(roles)}，当前角色为 {user.role}",
            )
        return user
    return _check


# 常用角色依赖 (作为 Annotated 类型使用)
AdminUser = Annotated[User, Depends(_role_checker("admin"))]
UploaderUser = Annotated[User, Depends(_role_checker("admin", "uploader"))]
AnnotatorUser = Annotated[User, Depends(_role_checker("admin", "annotator"))]
AnyUser = Annotated[User, Depends(_role_checker("admin", "uploader", "annotator"))]
