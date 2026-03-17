"""全局 pytest fixtures — SQLite / Redis 测试支持。"""
import asyncio
import os
from pathlib import Path
import uuid

import fitz
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import create_engine, text, types
from sqlalchemy.sql.elements import TextClause
from unittest.mock import AsyncMock, MagicMock


class SQLiteUUID(types.TypeDecorator):
    """SQLite 兼容的 UUID 类型。"""
    impl = types.String(32)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if isinstance(value, uuid.UUID):
                return value.hex
            return str(value).replace("-", "")
        return None

    def process_result_value(self, value, dialect):
        if value is not None:
            return uuid.UUID(value)
        return None


def _sqlite_compat():
    """PostgreSQL → SQLite 全类型适配。"""
    from pdf_sku.common.models import Base
    from sqlalchemy import ARRAY, Uuid
    try:
        from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
    except ImportError:
        JSONB = PG_UUID = None

    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, ARRAY):
                column.type = types.JSON()
            elif JSONB and isinstance(column.type, JSONB):
                column.type = types.JSON()
            elif isinstance(column.type, Uuid):
                column.type = SQLiteUUID()
            elif PG_UUID and isinstance(column.type, PG_UUID):
                column.type = SQLiteUUID()

            if column.server_default is not None:
                sd = column.server_default
                if hasattr(sd, 'arg') and isinstance(sd.arg, TextClause):
                    txt = str(sd.arg.text)
                    if 'interval' in txt.lower():
                        column.server_default = None


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine(tmp_path_factory):
    _sqlite_compat()
    from pdf_sku.common.models import Base
    db_path = tmp_path_factory.mktemp("sqlite") / "unit.sqlite3"
    sync_engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(sync_engine)
    sync_engine.dispose()

    eng = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncSession:
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        async with session.begin():
            yield session
            await session.rollback()


@pytest_asyncio.fixture
async def session_factory(engine):
    return async_sessionmaker(engine, expire_on_commit=False)


@pytest.fixture
def db_url() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+asyncpg://pdfsku:pdfsku@localhost:5432/pdfsku",
    )


@pytest.fixture
def db_schema() -> str:
    return f"test_{uuid.uuid4().hex}"


@pytest_asyncio.fixture
async def init_db(db_url: str, db_schema: str):
    from pdf_sku.common.models import Base

    engine = create_async_engine(
        db_url,
        echo=False,
        connect_args={"server_settings": {"search_path": db_schema}},
    )
    async with engine.begin() as conn:
        await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{db_schema}"'))
        await conn.execute(text(f'SET search_path TO "{db_schema}"'))
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.execute(text(f'DROP SCHEMA IF EXISTS "{db_schema}" CASCADE'))
    await engine.dispose()


@pytest_asyncio.fixture
async def redis_url():
    yield "redis://fakeredis/0"


@pytest_asyncio.fixture
async def fake_redis():
    from fakeredis.aioredis import FakeRedis

    redis = FakeRedis(decode_responses=True)
    try:
        yield redis
    finally:
        await redis.flushall()
        if hasattr(redis, "aclose"):
            await redis.aclose()
        else:
            await redis.close()


@pytest.fixture
def sample_pdf(tmp_path: Path) -> Path:
    doc = fitz.open()

    page1 = doc.new_page(width=612, height=792)
    page1.insert_text((50, 72), "Catalog 2026", fontsize=18)
    page1.insert_text((50, 110), "Model: XZ-500 Premium Widget", fontsize=12)
    page1.insert_text((50, 130), "Price: $29.99", fontsize=12)
    page1.insert_text((50, 150), "Material: Stainless Steel", fontsize=12)

    doc.new_page(width=612, height=792)

    pdf_path = tmp_path / "sample.pdf"
    doc.save(pdf_path)
    doc.close()
    return pdf_path


@pytest.fixture
def mock_redis():
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock(return_value=True)
    redis.delete = AsyncMock(return_value=1)
    redis.setex = AsyncMock(return_value=True)
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock(return_value=True)
    pipe = AsyncMock()
    pipe.__aenter__ = AsyncMock(return_value=pipe)
    pipe.__aexit__ = AsyncMock(return_value=False)
    pipe.execute = AsyncMock(return_value=[True])
    redis.pipeline = MagicMock(return_value=pipe)
    return redis


@pytest.fixture
def mock_llm():
    from pdf_sku.llm_adapter.client.base import LLMResponse
    llm = AsyncMock()
    llm.call_llm = AsyncMock(return_value=LLMResponse(
        content='{"page_type": "B", "confidence": 0.9}',
        model="mock", usage={"input_tokens": 100, "output_tokens": 50},
    ))
    return llm
