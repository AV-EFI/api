import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.core.db as db


def test_session_factory_supports_async_context_manager(monkeypatch):
    """The factory must be called before use as an async context manager.

    Regression test: async with get_async_session_maker() as session fails
    with "TypeError: 'async_sessionmaker' object does not support the
    asynchronous context manager protocol" because the factory itself is
    not an async context manager. The correct pattern is
    get_async_session_maker()(), which returns an AsyncSession that
    supports async with.
    """
    monkeypatch.setattr(
        db.settings,
        "DATABASE_URL",
        "postgresql+asyncpg://user:pass@localhost:5432/db",
    )

    maker = db.get_async_session_maker()
    assert isinstance(maker, async_sessionmaker)

    session = maker()
    assert isinstance(session, AsyncSession)
    assert hasattr(session, "__aenter__")
    assert hasattr(session, "__aexit__")

    async def enter():
        async with db.get_async_session_maker()() as entered:
            assert isinstance(entered, AsyncSession)

    asyncio.run(enter())
