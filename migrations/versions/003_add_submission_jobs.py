"""Add durable submission jobs and journals.

Revision ID: 003
Revises: 002
Create Date: 2026-11-02

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "submission_jobs",
        sa.Column("token", sa.String(length=36), nullable=False),
        sa.Column(
            "submitter_principal", sa.String(length=255), nullable=False
        ),
        sa.Column(
            "authentication_method", sa.String(length=32), nullable=False
        ),
        sa.Column("provider_handle", sa.String(length=255), nullable=False),
        sa.Column("prefix", sa.String(length=255), nullable=False),
        sa.Column("issuer_profile", sa.JSON(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("payload_bytes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("worker_id", sa.String(length=255), nullable=True),
        sa.Column(
            "lease_expires_at", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'running', 'succeeded', 'failed')",
            name="ck_submission_jobs_status",
        ),
        sa.PrimaryKeyConstraint("token"),
    )
    op.create_index(
        "ix_submission_jobs_principal_status",
        "submission_jobs",
        ["submitter_principal", "status"],
        unique=False,
    )
    op.create_index(
        "ix_submission_jobs_status_lease",
        "submission_jobs",
        ["status", "lease_expires_at"],
        unique=False,
    )
    op.create_index(
        "uq_submission_jobs_active_provider_handle",
        "submission_jobs",
        ["provider_handle"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_index(
        "ix_submission_jobs_provider_queue",
        "submission_jobs",
        ["provider_handle", "status", "created_at"],
        unique=False,
    )
    op.create_table(
        "submission_journal_entries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("submission_token", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("action", sa.String(length=16), nullable=True),
        sa.Column("pid", sa.String(length=255), nullable=True),
        sa.Column("local_id", sa.String(length=255), nullable=True),
        sa.Column("record_type", sa.String(length=255), nullable=True),
        sa.Column("error_code", sa.String(length=64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('succeeded', 'failed')",
            name="ck_submission_journal_entries_outcome",
        ),
        sa.ForeignKeyConstraint(
            ["submission_token"],
            ["submission_jobs.token"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "submission_token",
            "sequence",
            name="uq_submission_journal_entries_sequence",
        ),
    )


def downgrade() -> None:
    op.drop_table("submission_journal_entries")
    op.drop_index(
        "ix_submission_jobs_provider_queue", table_name="submission_jobs"
    )
    op.drop_index(
        "uq_submission_jobs_active_provider_handle",
        table_name="submission_jobs",
    )
    op.drop_index(
        "ix_submission_jobs_status_lease", table_name="submission_jobs"
    )
    op.drop_index(
        "ix_submission_jobs_principal_status", table_name="submission_jobs"
    )
    op.drop_table("submission_jobs")
