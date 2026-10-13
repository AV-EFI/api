"""Drop refresh_expires_at column and index.

Revision ID: 002
Revises: 001
Create Date: 2026-10-13

Refresh-token expiry is not part of the OAuth specification and is no longer
tracked. Only the access-token expiry is recorded.

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index(
        op.f("ix_oidc_sessions_refresh_expires_at"), table_name="oidc_sessions"
    )
    op.drop_column("oidc_sessions", "refresh_expires_at")


def downgrade() -> None:
    op.add_column(
        "oidc_sessions",
        sa.Column(
            "refresh_expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        op.f("ix_oidc_sessions_refresh_expires_at"),
        "oidc_sessions",
        ["refresh_expires_at"],
        unique=False,
    )
