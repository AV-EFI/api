from datetime import UTC, datetime

from app.models.session import OidcSession


def test_oidc_session_accepts_sid_in_init():
    """OidcSession must accept sid when constructed, like SessionStore.create.

    Regression test: sid was declared with init=False, so the dataclass
    __init__ rejected the sid=... keyword used by SessionStore.create,
    raising "TypeError: __init__() got an unexpected keyword argument
    'sid'". The caller always supplies sid (it is stored in the session
    cookie), so it must be a settable init field.
    """
    now = datetime.now(UTC)
    session = OidcSession(
        sid="abc-123",
        user_name="Ada",
        user_email="ada@example.com",
        user_uid="uid-1",
        user_orgid=None,
        audience="academiccloud",
        scopes=["openid", "profile"],
        access_token="access-token",
        refresh_token=None,
        id_token="id-token",
        access_expires_at=now,
        refresh_expires_at=None,
        login_time=now,
        updated_at=now,
    )

    assert isinstance(session, OidcSession)
    assert session.sid == "abc-123"
