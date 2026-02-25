"""数据库连接管理（延迟初始化）。"""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

engine = None
async_session_factory = None


def init_db(db_url, pool_size=10, max_overflow=20, echo=False):
    """初始化数据库引擎和会话工厂。应在 lifespan 中调用。"""
    global engine, async_session_factory
    engine = create_async_engine(
        db_url, pool_size=pool_size, max_overflow=max_overflow, echo=echo,
    )
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return engine, async_session_factory


async def ensure_tables(eng) -> None:
    """Create all tables that don't exist yet (e.g. newly added models)."""
    from pdf_sku.common.models import Base
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, checkfirst=True)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    if async_session_factory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
