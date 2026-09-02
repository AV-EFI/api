from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .config import settings

_engine = None
_async_session_maker = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL, pool_pre_ping=True
        )
    return _engine


def get_async_session_maker():
    global _async_session_maker
    if _async_session_maker is None:
        _async_session_maker = async_sessionmaker(
            get_engine(), expire_on_commit=False
        )
    return _async_session_maker


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database sessions."""
    async with get_async_session_maker() as session:
        yield session


async def close_db():
    """Close database connection pool."""
    global _engine
    if _engine:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None


engine = None
async_session_maker = None
