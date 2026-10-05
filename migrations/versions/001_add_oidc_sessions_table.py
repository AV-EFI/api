"""Add oidc_sessions table.

Revision ID: 001
Revises:
Create Date: 2026-09-02

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oidc_sessions",
        sa.Column("sid", sa.String(length=36), nullable=False),
        sa.Column("user_name", sa.String(length=255), nullable=False),
        sa.Column("user_email", sa.String(length=255), nullable=False),
        sa.Column("user_uid", sa.String(length=255), nullable=False),
        sa.Column("user_orgid", sa.String(length=255), nullable=True),
        sa.Column("audience", sa.String(length=255), nullable=False),
        sa.Column("scopes", sa.JSON(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("id_token", sa.Text(), nullable=False),
        sa.Column(
            "access_expires_at", sa.TIMESTAMP(timezone=True), nullable=False
        ),
        sa.Column(
            "refresh_expires_at", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("login_time", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("sid"),
    )
    op.create_index(
        op.f("ix_oidc_sessions_refresh_expires_at"),
        "oidc_sessions",
        ["refresh_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_oidc_sessions_refresh_expires_at"), table_name="oidc_sessions"
    )
    op.drop_table("oidc_sessions")
