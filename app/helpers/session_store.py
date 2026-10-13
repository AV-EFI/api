from datetime import UTC

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.helpers.auth import derive_access_expiry
from app.models.session import OidcSession


class SessionStore:
    """Async session store for OIDC tokens backed by Postgres."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get(self, sid: str) -> OidcSession | None:
        """Get session by sid. Returns None if not found."""
        stmt = select(OidcSession).where(OidcSession.sid == sid)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(
        self,
        sid: str,
        user_name: str,
        user_email: str,
        user_uid: str,
        user_orgid: str | None,
        audience: str,
        scopes: list[str],
        access_token: str,
        refresh_token: str | None,
        id_token: str,
        access_expires_at: int,
    ) -> OidcSession:
        """Create a new session."""
        from datetime import datetime

        now = datetime.now(UTC)
        access_expires_dt = datetime.fromtimestamp(access_expires_at, tz=UTC)

        session = OidcSession(
            sid=sid,
            user_name=user_name,
            user_email=user_email,
            user_uid=user_uid,
            user_orgid=user_orgid,
            audience=audience,
            scopes=scopes,
            access_token=access_token,
            refresh_token=refresh_token,
            id_token=id_token,
            access_expires_at=access_expires_dt,
            login_time=now,
            updated_at=now,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def update_tokens(
        self, session: OidcSession, new_tokens: dict
    ) -> OidcSession:
        """Update session with fresh tokens from refresh.

        Args:
            session: Existing session to update
            new_tokens: Token dict from authlib (access_token,
                refresh_token, expires_at, ...)

        Returns
        -------
            Updated session
        """
        from datetime import datetime

        now = datetime.now(UTC)
        access_expires_at = derive_access_expiry(new_tokens)

        session.access_token = new_tokens["access_token"]
        # Keep the current refresh token if the provider does not rotate it.
        session.refresh_token = new_tokens.get(
            "refresh_token", session.refresh_token
        )
        session.access_expires_at = access_expires_at
        session.updated_at = now

        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def delete(self, session: OidcSession) -> None:
        """Delete a session."""
        await self.db.delete(session)
        await self.db.commit()

    def to_dict(self, session: OidcSession) -> dict:
        """Convert OidcSession to plain dict for use with helpers."""
        return {
            "user": {
                "name": session.user_name,
                "email": session.user_email,
                "uid": session.user_uid,
                "orgid": session.user_orgid,
            },
            "audience": session.audience,
            "scopes": session.scopes,
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "id_token": session.id_token,
            "access_expires_at": int(session.access_expires_at.timestamp()),
            "login_time": int(session.login_time.timestamp()),
            "updated_at": int(session.updated_at.timestamp()),
        }
