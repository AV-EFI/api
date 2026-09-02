from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
)


class Base(MappedAsDataclass, DeclarativeBase):
    pass


class OidcSession(Base):
    __tablename__ = "oidc_sessions"

    sid: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        init=False,
        default_factory=lambda: str(uuid4()),
    )
    user_name: Mapped[str] = mapped_column(String(255))
    user_email: Mapped[str] = mapped_column(String(255))
    user_uid: Mapped[str] = mapped_column(String(255))
    user_orgid: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    audience: Mapped[str] = mapped_column(String(255))
    scopes: Mapped[list[str]] = mapped_column(JSON)
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )
    id_token: Mapped[str] = mapped_column(Text)
    access_expires_at: Mapped[datetime] = mapped_column()
    refresh_expires_at: Mapped[datetime | None] = mapped_column(
        nullable=True
    )
    login_time: Mapped[datetime] = mapped_column()
    updated_at: Mapped[datetime] = mapped_column(
        default_factory=lambda: datetime.now(UTC)
    )
