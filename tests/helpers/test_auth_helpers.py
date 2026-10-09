from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from app.helpers.auth import classify, delete_expired_sessions


def _session_dict(
    *,
    access_expires_at: int,
    refresh_expires_at: int | None,
) -> dict:
    return {
        "access_expires_at": access_expires_at,
        "refresh_expires_at": refresh_expires_at,
    }


def _now() -> int:
    return int(datetime.now(UTC).timestamp())


def test_classify_active_with_no_refresh_expiry():
    now = _now()
    session = _session_dict(
        access_expires_at=now + 100,
        refresh_expires_at=None,
    )
    assert classify(session) == "active"


def test_classify_active_with_future_refresh_expiry():
    now = _now()
    session = _session_dict(
        access_expires_at=now + 100,
        refresh_expires_at=now + 1000,
    )
    assert classify(session) == "active"


def test_classify_refreshable_with_expired_access_and_future_refresh():
    now = _now()
    session = _session_dict(
        access_expires_at=now - 10,
        refresh_expires_at=now + 1000,
    )
    assert classify(session) == "refreshable"


def test_classify_expired_when_no_refresh_expiry():
    now = _now()
    session = _session_dict(
        access_expires_at=now - 10,
        refresh_expires_at=None,
    )
    assert classify(session) == "expired"


def test_classify_expired_when_access_and_refresh_expired():
    now = _now()
    session = _session_dict(
        access_expires_at=now - 100,
        refresh_expires_at=now - 10,
    )
    assert classify(session) == "expired"


def test_delete_expired_sessions_executes_and_compiles():
    """Cleanup statement must be valid SQL, not a tuple.

    Regression test: the where() clause used a Python tuple on the right-hand
    side of the OR, raising "SQL expression for WHERE/HAVING role expected,
    got (<BinaryExpression>, <BinaryExpression>)". The statement is built
    inside delete_expired_sessions and captured from db.execute.
    """
    db = MagicMock()
    db.execute = AsyncMock()
    result = MagicMock()
    result.rowcount = 3
    db.execute.return_value = result
    db.commit = AsyncMock()

    deleted = _run_delete(db)

    assert deleted == 3
    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()

    stmt = db.execute.await_args.args[0]
    compiled = stmt.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "DELETE FROM oidc_sessions" in sql
    assert "WHERE" in sql
    # Both branches of the OR must be present.
    assert "refresh_expires_at" in sql
    assert "access_expires_at" in sql


def _run_delete(db):
    import asyncio

    return asyncio.run(delete_expired_sessions(db))
