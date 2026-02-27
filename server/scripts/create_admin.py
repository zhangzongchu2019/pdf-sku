#!/usr/bin/env python3
"""
创建第一个 admin 账号的初始化脚本。

用法:
    cd server
    PYTHONPATH=src python scripts/create_admin.py
    PYTHONPATH=src python scripts/create_admin.py --username admin --password mypassword
"""
from __future__ import annotations
import argparse
import asyncio
import hashlib
import hmac
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000).hex()
    return f"{salt.hex()}${h}"


async def create_admin(username: str, password: str) -> None:
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select, func

    # 读取数据库连接
    db_url = os.environ.get(
        "DATABASE_URL",
        "postgresql+asyncpg://pdfsku:pdfsku@localhost:5432/pdfsku",
    )

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        from pdf_sku.common.models import User

        # 检查是否已存在
        existing = await session.execute(
            select(func.count()).select_from(User).where(User.username == username)
        )
        if existing.scalar():
            print(f"[ERROR] 用户名 '{username}' 已存在，请换一个用户名或直接登录。")
            return

        user = User(
            username=username,
            display_name=username,
            password_hash=hash_password(password),
            role="admin",
            is_active=True,
        )
        session.add(user)
        await session.commit()
        print(f"[OK] admin 账号已创建:")
        print(f"     用户名: {username}")
        print(f"     密码:   {password}")
        print(f"     角色:   admin")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="创建初始 admin 账号")
    parser.add_argument("--username", default="admin", help="管理员用户名 (默认: admin)")
    parser.add_argument("--password", default=None, help="管理员密码 (不指定则交互输入)")
    args = parser.parse_args()

    password = args.password
    if not password:
        import getpass
        password = getpass.getpass(f"请输入 '{args.username}' 的密码 (至少6位): ")
        if len(password) < 6:
            print("[ERROR] 密码至少需要 6 位")
            sys.exit(1)
        confirm = getpass.getpass("确认密码: ")
        if password != confirm:
            print("[ERROR] 两次密码不一致")
            sys.exit(1)

    asyncio.run(create_admin(args.username, password))


if __name__ == "__main__":
    main()
