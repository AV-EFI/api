"""Add worker retry state and deterministic PID plan.

Revision ID: 004
Revises: 003
Create Date: 2026-11-09

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "submission_jobs",
        sa.Column(
            "next_attempt_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_submission_jobs_status_next_attempt",
        "submission_jobs",
        ["status", "next_attempt_at"],
        unique=False,
    )
    op.create_table(
        "submission_pid_plan",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("submission_token", sa.String(length=36), nullable=False),
        sa.Column("identifier_category", sa.String(length=64), nullable=False),
        sa.Column("identifier_id", sa.String(length=255), nullable=False),
        sa.Column("planned_pid", sa.String(length=255), nullable=False),
        sa.Column("local_id", sa.String(length=255), nullable=True),
        sa.Column("record_type", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["submission_token"],
            ["submission_jobs.token"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "submission_token",
            "identifier_category",
            "identifier_id",
            name="uq_submission_pid_plan_record",
        ),
    )
    op.create_index(
        "ix_submission_pid_plan_token",
        "submission_pid_plan",
        ["submission_token"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_submission_pid_plan_token", table_name="submission_pid_plan"
    )
    op.drop_table("submission_pid_plan")
    op.drop_index(
        "ix_submission_jobs_status_next_attempt",
        table_name="submission_jobs",
    )
    op.drop_column("submission_jobs", "next_attempt_at")
