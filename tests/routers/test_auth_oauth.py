import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routers.auth import auth, redirect_to_ac, settings
from app.routers.auth import oauth as oauth_app


def _request(headers=None, query_params=None):
    url = SimpleNamespace(path="/rest/v1/auth/callback/academiccloud")
    req = SimpleNamespace()
    req.url_for = MagicMock(return_value=url)
    req.headers = headers or {}
    req.query_params = SimpleNamespace(
        get=lambda k: (query_params or {}).get(k)
    )
    req.session = {}
    return req


def _run(coro):
    return asyncio.run(coro)


def test_signin_missing_client_id_returns_500():
    with (
        patch.object(settings, "AC_CLIENT_ID", ""),
        pytest.raises(Exception) as excinfo,
    ):
        _run(redirect_to_ac(_request()))
    assert excinfo.value.status_code == 500


def test_signin_accepts_http_forwarded_proto():
    with (
        patch.object(settings, "AC_CLIENT_ID", "cid"),
        patch.object(
            oauth_app.academiccloud,
            "authorize_redirect",
            new=AsyncMock(return_value="redir"),
        ) as authorize,
    ):
        result = _run(
            redirect_to_ac(
                _request(
                    headers={
                        "x-forwarded-host": "app.example.org",
                        "x-forwarded-proto": "https",
                    }
                )
            )
        )
    assert result == "redir"
    authorize.assert_awaited_once()


def test_signin_rejects_invalid_forwarded_proto():
    with (
        patch.object(settings, "AC_CLIENT_ID", "cid"),
        pytest.raises(Exception) as excinfo,
    ):
        _run(
            redirect_to_ac(
                _request(
                    headers={
                        "x-forwarded-host": "app.example.org",
                        "x-forwarded-proto": "ftp",
                    }
                )
            )
        )
    assert excinfo.value.status_code == 400


def test_callback_missing_code_returns_400():
    with pytest.raises(Exception) as excinfo:
        _run(auth(_request(query_params={"state": "abc"}), MagicMock()))
    assert excinfo.value.status_code == 400


def test_callback_missing_state_returns_400():
    with pytest.raises(Exception) as excinfo:
        _run(auth(_request(query_params={"code": "xyz"}), MagicMock()))
    assert excinfo.value.status_code == 400


def test_callback_provider_error_returns_400():
    with pytest.raises(Exception) as excinfo:
        _run(
            auth(
                _request(query_params={"error": "access_denied"}),
                MagicMock(),
            )
        )
    assert excinfo.value.status_code == 400


def test_callback_state_mismatch_returns_400():
    from authlib.integrations.base_client.errors import MismatchingStateError

    with (
        patch.object(
            oauth_app.academiccloud,
            "authorize_access_token",
            new=AsyncMock(side_effect=MismatchingStateError()),
        ),
        pytest.raises(Exception) as excinfo,
    ):
        _run(
            auth(
                _request(query_params={"code": "c", "state": "s"}),
                MagicMock(),
            )
        )
    assert excinfo.value.status_code == 400


def test_callback_missing_userinfo_returns_502():
    token = {"access_token": "at", "expires_at": 9999999999}
    with (
        patch.object(
            oauth_app.academiccloud,
            "authorize_access_token",
            new=AsyncMock(return_value=token),
        ),
        pytest.raises(Exception) as excinfo,
    ):
        _run(
            auth(
                _request(query_params={"code": "c", "state": "s"}),
                MagicMock(),
            )
        )
    assert excinfo.value.status_code == 502


def test_callback_valid_creates_session_and_redirects():
    token = {
        "access_token": "at",
        "expires_at": 9999999999,
        "scope": "openid email",
        "refresh_token": "rt",
        "id_token": "it",
        "userinfo": {
            "name": "Ada",
            "email": "ada@example.com",
            "uid": "uid-1",
            "ou": "org",
            "aud": "audience",
        },
    }
    db = MagicMock()
    with (
        patch.object(
            oauth_app.academiccloud,
            "authorize_access_token",
            new=AsyncMock(return_value=token),
        ),
        patch("app.routers.auth.SessionStore") as store_cls,
    ):
        store = MagicMock()
        store.create = AsyncMock()
        store_cls.return_value = store
        result = _run(
            auth(_request(query_params={"code": "c", "state": "s"}), db)
        )

    assert result.status_code in (302, 307)
    store.create.assert_awaited_once()
