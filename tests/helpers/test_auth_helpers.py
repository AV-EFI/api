import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.dialects import postgresql

from app.helpers.auth import (
    classify,
    delete_expired_sessions,
    derive_access_expiry,
    revoke_provider_token,
)


def _session_dict(*, access_expires_at: int) -> dict:
    return {
        "access_expires_at": access_expires_at,
    }


def _now() -> int:
    return int(datetime.now(UTC).timestamp())


def test_classify_active_with_future_access_expiry():
    now = _now()
    session = _session_dict(access_expires_at=now + 100)
    assert classify(session) == "active"


def test_classify_expired_with_past_access_expiry():
    now = _now()
    session = _session_dict(access_expires_at=now - 10)
    assert classify(session) == "expired"


def test_derive_access_expiry_ignores_refresh_expires_in():
    token = {
        "expires_at": 1700000000,
        "refresh_expires_in": 1800,
    }
    expiry = derive_access_expiry(token)
    assert int(expiry.timestamp()) == 1700000000


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
    assert "access_expires_at" in sql
    assert "refresh_expires_at" not in sql


def _run_delete(db):
    import asyncio

    return asyncio.run(delete_expired_sessions(db))


def test_revoke_provider_token_without_endpoint():
    result = asyncio.run(
        revoke_provider_token(
            client_id="cid",
            client_secret="secret",
            metadata={},
            refresh_token="rt",
            access_token="at",
        )
    )
    assert result is False


def test_revoke_provider_token_without_tokens():
    result = asyncio.run(
        revoke_provider_token(
            client_id="cid",
            client_secret="secret",
            metadata={"revocation_endpoint": "https://idp/revoke"},
            refresh_token=None,
            access_token=None,
        )
    )
    assert result is False


def _revocation_client():
    response = MagicMock()
    response.raise_for_status = MagicMock(return_value=None)
    client = MagicMock()
    client.revoke_token = AsyncMock(return_value=response)
    client.aclose = AsyncMock()
    return client


def test_revoke_provider_token_prefers_refresh_token():
    client = _revocation_client()

    with patch(
        "app.helpers.auth.AsyncOAuth2Client", return_value=client
    ) as client_cls:
        result = asyncio.run(
            revoke_provider_token(
                client_id="cid",
                client_secret="secret",
                metadata={"revocation_endpoint": "https://idp/revoke"},
                refresh_token="rt",
                access_token="at",
            )
        )

    assert result is True
    client_cls.assert_called_once_with(client_id="cid", client_secret="secret")
    client.revoke_token.assert_awaited_once_with(
        "https://idp/revoke",
        token="rt",
        token_type_hint="refresh_token",
    )
    client.aclose.assert_awaited_once()


def test_revoke_provider_token_falls_back_to_access_token():
    client = _revocation_client()

    with patch("app.helpers.auth.AsyncOAuth2Client", return_value=client):
        result = asyncio.run(
            revoke_provider_token(
                client_id="cid",
                client_secret="secret",
                metadata={"revocation_endpoint": "https://idp/revoke"},
                refresh_token=None,
                access_token="at",
            )
        )

    assert result is True
    client.revoke_token.assert_awaited_once_with(
        "https://idp/revoke",
        token="at",
        token_type_hint="access_token",
    )
    client.aclose.assert_awaited_once()


def test_revoke_provider_token_raises_on_provider_error():
    client = MagicMock()
    response = MagicMock()
    response.raise_for_status = MagicMock(
        side_effect=RuntimeError("provider rejected")
    )
    client.revoke_token = AsyncMock(return_value=response)
    client.aclose = AsyncMock()

    with patch("app.helpers.auth.AsyncOAuth2Client", return_value=client):
        try:
            asyncio.run(
                revoke_provider_token(
                    client_id="cid",
                    client_secret="secret",
                    metadata={"revocation_endpoint": "https://idp/revoke"},
                    refresh_token="rt",
                    access_token=None,
                )
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Expected RuntimeError")

    client.aclose.assert_awaited_once()
