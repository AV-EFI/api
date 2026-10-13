from datetime import UTC, datetime

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.models.session import OidcSession


def _table_ddl() -> str:
    return str(
        CreateTable(OidcSession.__table__).compile(
            dialect=postgresql.dialect()
        )
    )


def test_oidc_session_datetime_columns_are_timezone_aware():
    """OidcSession datetime columns must map to timestamptz.

    Regression test: the columns were declared as plain Mapped[datetime],
    which SQLAlchemy infers as TIMESTAMP WITHOUT TIME ZONE. The application
    writes timezone-aware datetimes (UTC), and asyncpg's timestamp_encode
    then computes aware - naive_epoch, raising
    "TypeError: can't subtract offset-naive and offset-aware datetimes".
    They must map to TIMESTAMP WITH TIME ZONE, matching the Alembic
    migration, so the table accepts aware datetimes.
    """
    ddl = _table_ddl()
    for col in (
        "access_expires_at",
        "login_time",
        "updated_at",
    ):
        assert f"{col} TIMESTAMP WITH TIME ZONE" in ddl, (
            f"{col} should be timestamptz, got: {ddl}"
        )
    assert "refresh_expires_at" not in ddl


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
        login_time=now,
        updated_at=now,
    )

    assert isinstance(session, OidcSession)
    assert session.sid == "abc-123"
