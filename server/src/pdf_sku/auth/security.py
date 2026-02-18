"""密码哈希 + JWT 工具。"""
from __future__ import annotations
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt, JWTError

# ── 配置 ──
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", secrets.token_urlsafe(48))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("JWT_EXPIRE_MINUTES", "480"))  # 8h


# ────────────────── 密码哈希 (sha256 + salt, 无需额外依赖) ──────────────────

def _hash(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000).hex()


def hash_password(password: str) -> str:
    """返回 salt$hash 格式的密码哈希。"""
    salt = os.urandom(16)
    h = _hash(password, salt)
    return f"{salt.hex()}${h}"


def verify_password(plain: str, hashed: str) -> bool:
    """验证密码。"""
    try:
        salt_hex, expected = hashed.split("$", 1)
        salt = bytes.fromhex(salt_hex)
        return hmac.compare_digest(_hash(plain, salt), expected)
    except Exception:
        return False


# ────────────────── JWT ──────────────────

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    """解码 JWT, 失败抛 JWTError。"""
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
