import asyncio
import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool


def run(coro):
    """Run one async scenario in the style used by the rest of the suite."""
    return asyncio.run(coro)


@pytest.fixture(scope="session")
def postgres_url() -> str:
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL is not set")
    database = make_url(url).database or ""
    if "test" not in database:
        pytest.fail("Refusing to run live tests against a non-test database")
    return url


async def truncate_database(url: str) -> None:
    engine = create_async_engine(url, poolclass=NullPool)
    try:
        async with engine.begin() as connection:
            await connection.execute(
                text(
                    "TRUNCATE submission_pid_plan,"
                    " submission_journal_entries,"
                    " submission_jobs"
                    " RESTART IDENTITY CASCADE"
                )
            )
    finally:
        await engine.dispose()


@pytest.fixture(autouse=True)
def clean_database(postgres_url):
    try:
        run(truncate_database(postgres_url))
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            "Live database schema is missing; run 'alembic upgrade head'"
            f" first ({exc})"
        )
    yield
    run(truncate_database(postgres_url))
