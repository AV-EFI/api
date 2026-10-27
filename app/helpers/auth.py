from datetime import UTC, datetime, timedelta

from authlib.integrations.httpx_client import AsyncOAuth2Client
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.session import OidcSession
from app.schemas.auth import SessionInfo, User


def derive_access_expiry(token: dict) -> datetime:
    """Extract the access-token expiry from a token response.

    Only the standard ``expires_at`` is used. The provider-specific
    ``refresh_expires_in`` field is intentionally ignored because refresh-token
    expiry is not part of the OAuth specification.
    """
    return datetime.fromtimestamp(token["expires_at"], tz=UTC)


def classify(session: dict) -> str:
    """Classify session state based on the access-token expiry.

    Returns one of: "active", "expired"
    """
    now = int(datetime.now(UTC).timestamp())
    access_expires_at = session.get("access_expires_at", 0)

    if now < access_expires_at:
        return "active"
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
    """Delete sessions beyond the server-side session lifetime.

    Access-token expiry is not a session expiry boundary: a valid refresh
    token must survive access-token expiry so the next activity can rotate it.
    The signed browser cookie and database row share the configured session
    lifetime, measured from the original login.

    Returns
    -------
        Number of rows deleted.
    """
    now = datetime.now(UTC)
    session_expired_before = now - timedelta(
        seconds=settings.SESSION_COOKIE_MAX_AGE
    )

    stmt = delete(OidcSession).where(
        OidcSession.login_time < session_expired_before
    )

    result = await db.execute(stmt)
    await db.commit()
    return result.rowcount


async def revoke_provider_token(
    *,
    client_id: str,
    client_secret: str,
    metadata: dict,
    refresh_token: str | None,
    access_token: str | None,
) -> bool:
    """Revoke a provider token (RFC 7009).

    Prefers the refresh token, falling back to the access token. Returns True
    when a revocation request was actually sent and accepted, False when no
    revocation endpoint or token was available. Raises when the provider
    rejects the revocation request.

    The ``id_token`` is never sent to the revocation endpoint. Token values are
    never logged by this function.
    """
    revocation_endpoint = metadata.get("revocation_endpoint")
    if not revocation_endpoint:
        return False
    if refresh_token:
        token, token_type_hint = refresh_token, "refresh_token"
    elif access_token:
        token, token_type_hint = access_token, "access_token"
    else:
        return False

    client = AsyncOAuth2Client(
        client_id=client_id,
        client_secret=client_secret,
    )
    try:
        response = await client.revoke_token(
            revocation_endpoint,
            token=token,
            token_type_hint=token_type_hint,
        )
        response.raise_for_status()
    finally:
        await client.aclose()
    return True
