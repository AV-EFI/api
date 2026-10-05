from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import OidcSession
from app.schemas.auth import SessionInfo, User


def derive_expiries(
    token: dict,
) -> tuple[datetime, datetime | None]:
    """Extract access and refresh expiry datetimes from token response.

    Args:
        token: Token dict from authlib with 'expires_at' and
            optionally 'refresh_expires_in'

    Returns
    -------
        (access_expires_at, refresh_expires_at) where refresh_expires_at
        is None if unavailable
    """
    access_expires_at = datetime.fromtimestamp(token["expires_at"], tz=UTC)

    refresh_expires_at: datetime | None = None
    if "refresh_expires_in" in token:
        refresh_expires_at = datetime.fromtimestamp(
            token["expires_at"] + token["refresh_expires_in"],
            tz=UTC,
        )

    return access_expires_at, refresh_expires_at


def classify(session: dict) -> str:
    """Classify session state based on expiry timestamps.

    Returns one of: "active", "refreshable", "expired"
    """
    now = int(datetime.now(UTC).timestamp())
    access_expires_at = session.get("access_expires_at", 0)
    refresh_expires_at = session.get("refresh_expires_at")

    if now < access_expires_at:
        return "active"
    if refresh_expires_at is None or now < refresh_expires_at:
        return "refreshable"
    return "expired"


def build_session_info(session: dict) -> SessionInfo:
    """Build SessionInfo for frontend, excluding raw tokens."""
    now = int(datetime.now(UTC).timestamp())

    user = None
    if session.get("user"):
        user = User(
            name=session["user"]["name"],
            email=session["user"]["email"],
            uid=session["user"]["uid"],
            orgid=session["user"].get("orgid"),
        )

    expires_at: int | None = None
    if "refresh_expires_at" in session and session["refresh_expires_at"]:
        expires_at = int(session["refresh_expires_at"])
    elif "access_expires_at" in session:
        expires_at = int(session["access_expires_at"])

    return SessionInfo(
        authenticated=True,
        user=user,
        scopes=session.get("scopes", []),
        audience=session.get("audience"),
        server_time=now,
        expires_at=expires_at,
    )


async def delete_expired_sessions(db: AsyncSession) -> int:
    """Delete sessions whose tokens have expired.

    Returns
    -------
        Number of rows deleted.
    """
    now = datetime.now(UTC)

    stmt = delete(OidcSession).where(
        (OidcSession.refresh_expires_at < now)
        | (
            OidcSession.refresh_expires_at.is_(None),
            OidcSession.access_expires_at < now,
        )
    )

    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount
