from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    TIMESTAMP,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from .session import Base

JOB_STATUSES = ("queued", "running", "succeeded", "failed")
JOURNAL_OUTCOMES = ("succeeded", "failed")


class SubmissionJob(Base):
    """Durable state for one submitted AVefi batch."""

    __tablename__ = "submission_jobs"
    __table_args__ = (
        CheckConstraint(
            f"status IN {JOB_STATUSES}", name="ck_submission_jobs_status"
        ),
        Index(
            "ix_submission_jobs_principal_status",
            "submitter_principal",
            "status",
        ),
        Index(
            "ix_submission_jobs_status_lease",
            "status",
            "lease_expires_at",
        ),
        Index(
            "uq_submission_jobs_active_provider_handle",
            "provider_handle",
            unique=True,
            postgresql_where=text("status = 'running'"),
        ),
        Index(
            "ix_submission_jobs_provider_queue",
            "provider_handle",
            "status",
            "created_at",
        ),
    )

    token: Mapped[str] = mapped_column(String(36), primary_key=True)
    submitter_principal: Mapped[str] = mapped_column(String(255))
    authentication_method: Mapped[str] = mapped_column(String(32))
    provider_handle: Mapped[str] = mapped_column(String(255))
    prefix: Mapped[str] = mapped_column(String(255))
    issuer_profile: Mapped[dict[str, str]] = mapped_column(JSON)
    payload: Mapped[dict | list] = mapped_column(JSON)
    payload_digest: Mapped[str] = mapped_column(String(64))
    record_count: Mapped[int] = mapped_column(Integer)
    payload_bytes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    worker_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default_factory=lambda: datetime.now(UTC),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True, default=None
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default_factory=lambda: datetime.now(UTC),
    )
    failure_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None
    )
    failure_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )


class SubmissionJournalEntry(Base):
    """Durable checkpoint for one successful or failed submission operation."""

    __tablename__ = "submission_journal_entries"
    __table_args__ = (
        CheckConstraint(
            f"outcome IN {JOURNAL_OUTCOMES}",
            name="ck_submission_journal_entries_outcome",
        ),
        UniqueConstraint(
            "submission_token",
            "sequence",
            name="uq_submission_journal_entries_sequence",
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )
    submission_token: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("submission_jobs.token", ondelete="CASCADE"),
    )
    sequence: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16))
    action: Mapped[str | None] = mapped_column(
        String(16), nullable=True, default=None
    )
    pid: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )
    local_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )
    record_type: Mapped[str | None] = mapped_column(
        String(255), nullable=True, default=None
    )
    error_code: Mapped[str | None] = mapped_column(
        String(64), nullable=True, default=None
    )
    error_message: Mapped[str | None] = mapped_column(
        Text, nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        default_factory=lambda: datetime.now(UTC),
    )
