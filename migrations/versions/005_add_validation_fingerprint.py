"""Record the validator fingerprint on accepted submissions.

Revision ID: 005
Revises: 004
Create Date: 2026-11-23

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "submission_jobs",
        sa.Column("validation_fingerprint", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("submission_jobs", "validation_fingerprint")
