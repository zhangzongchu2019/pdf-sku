"""LLM Account CRUD — 只增删不改。"""
from __future__ import annotations

from sqlalchemy import select, delete as sa_delete
from sqlalchemy.ext.asyncio import AsyncSession

from pdf_sku.common.models import LLMAccount
from pdf_sku.common.crypto import encrypt_value, decrypt_value


def _mask_key(raw: str) -> str:
    """Show first 4 + last 4 chars: 'sk-5Gxx...1234'."""
    if len(raw) <= 8:
        return raw[:2] + "***"
    return raw[:4] + "..." + raw[-4:]


async def list_accounts(db: AsyncSession) -> list[dict]:
    """List all accounts (key masked)."""
    result = await db.execute(select(LLMAccount).order_by(LLMAccount.id))
    accounts = result.scalars().all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "provider_type": a.provider_type,
            "api_base": a.api_base,
            "api_key_masked": "****" + a.encrypted_api_key[-6:] if a.encrypted_api_key else "***",
            "created_at": a.created_at.isoformat() if a.created_at else None,
        }
        for a in accounts
    ]


async def create_account(
    db: AsyncSession,
    name: str,
    provider_type: str,
    api_base: str,
    api_key: str,
    secret: str,
) -> dict:
    """Create a new LLM account with encrypted api_key."""
    encrypted = encrypt_value(api_key, secret)
    account = LLMAccount(
        name=name,
        provider_type=provider_type,
        api_base=api_base or "",
        encrypted_api_key=encrypted,
    )
    db.add(account)
    await db.flush()
    return {
        "id": account.id,
        "name": account.name,
        "provider_type": account.provider_type,
        "api_base": account.api_base,
        "api_key_masked": _mask_key(api_key),
        "created_at": account.created_at.isoformat() if account.created_at else None,
    }


async def delete_account(db: AsyncSession, account_id: int) -> bool:
    """Delete an account by ID."""
    result = await db.execute(
        sa_delete(LLMAccount).where(LLMAccount.id == account_id)
    )
    return result.rowcount > 0


async def get_account_api_key(
    db: AsyncSession,
    name: str,
    secret: str,
) -> tuple[str, str]:
    """Return (decrypted api_key, api_base) for the named account."""
    result = await db.execute(
        select(LLMAccount).where(LLMAccount.name == name)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise ValueError(f"LLM account '{name}' not found")
    api_key = decrypt_value(account.encrypted_api_key, secret)
    return api_key, account.api_base


async def account_exists(db: AsyncSession, name: str) -> bool:
    """Check if an account with the given name exists."""
    result = await db.execute(
        select(LLMAccount.id).where(LLMAccount.name == name)
    )
    return result.scalar_one_or_none() is not None
