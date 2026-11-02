from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import (
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models import submission  # noqa: F401
from app.models.session import Base

target_metadata = Base.metadata


def run_migrations_offline(url: str) -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(conn: Connection) -> None:
    context.configure(
        connection=conn,
        target_metadata=target_metadata,
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    connectable = create_async_engine(
        settings.DATABASE_URL,
        poolclass=NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline(settings.DATABASE_URL)
else:
    import asyncio

    asyncio.run(run_migrations_online())
