"""全局 pytest fixtures — SQLite 内存库 (UUID/ARRAY/JSONB 适配)。"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy import types, event
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
import uuid


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
async def engine():
    _sqlite_compat()
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    from pdf_sku.common.models import Base
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
