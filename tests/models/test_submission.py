from datetime import UTC, datetime

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.models.submission import (
    SubmissionJob,
    SubmissionJournalEntry,
    SubmissionPidPlan,
)


def _table_ddl(model) -> str:
    return str(
        CreateTable(model.__table__).compile(dialect=postgresql.dialect())
    )


def test_submission_datetime_columns_are_timezone_aware():
    job_ddl = _table_ddl(SubmissionJob)
    journal_ddl = _table_ddl(SubmissionJournalEntry)

    for col in (
        "lease_expires_at",
        "next_attempt_at",
        "created_at",
        "started_at",
        "finished_at",
        "updated_at",
    ):
        assert f"{col} TIMESTAMP WITH TIME ZONE" in job_ddl
    assert "created_at TIMESTAMP WITH TIME ZONE" in journal_ddl
    assert "created_at TIMESTAMP WITH TIME ZONE" in _table_ddl(
        SubmissionPidPlan
    )


def test_submission_job_constraints_and_indexes():
    ddl = _table_ddl(SubmissionJob)
    index_ddl = {
        index.name: str(
            CreateIndex(index).compile(dialect=postgresql.dialect())
        )
        for index in SubmissionJob.__table__.indexes
    }

    assert "ck_submission_jobs_status" in ddl
    assert "status IN ('queued', 'running', 'succeeded', 'failed')" in ddl
    assert "uq_submission_jobs_active_provider_handle" in index_ddl
    assert (
        "WHERE status = 'running'"
        in index_ddl["uq_submission_jobs_active_provider_handle"]
    )
    assert "ix_submission_jobs_provider_queue" in index_ddl
    assert "ix_submission_jobs_status_next_attempt" in index_ddl
    assert "record_count INTEGER" in ddl
    assert "payload_bytes INTEGER" in ddl


def test_submission_journal_constraints_and_error_fields():
    ddl = _table_ddl(SubmissionJournalEntry)

    assert "ck_submission_journal_entries_outcome" in ddl
    assert "outcome IN ('succeeded', 'failed')" in ddl
    assert "uq_submission_journal_entries_sequence" in ddl
    assert (
        "FOREIGN KEY(submission_token) REFERENCES submission_jobs (token)"
        in ddl
    )
    assert "error_code VARCHAR(64)" in ddl
    assert "error_message TEXT" in ddl


def test_submission_pid_plan_constraints():
    ddl = _table_ddl(SubmissionPidPlan)

    assert "uq_submission_pid_plan_record" in ddl
    assert "FOREIGN KEY(submission_token)" in ddl
    assert "ON DELETE CASCADE" in ddl
    assert "planned_pid VARCHAR(255)" in ddl


def test_submission_models_accept_job_and_failure_checkpoint_values():
    now = datetime.now(UTC)
    job = SubmissionJob(
        token="submission-token-1",
        submitter_principal="SDK",
        authentication_method="basic",
        provider_handle="21.11155/SDK",
        prefix="21.11155",
        issuer_profile={
            "has_issuer_name": "Stiftung Deutsche Kinemathek",
            "has_issuer_id": "https://w3id.org/isil/DE-MUS-407010",
        },
        payload=[{"category": "avefi:WorkVariant"}],
        payload_digest="a" * 64,
        record_count=1,
        payload_bytes=32,
        status="queued",
        created_at=now,
        updated_at=now,
    )
    entry = SubmissionJournalEntry(
        submission_token=job.token,
        sequence=1,
        outcome="failed",
        action="CREATE",
        local_id="150003397",
        record_type="WorkVariant",
        error_code="handle_unavailable",
        error_message=(
            "Handle CREATE failed because the service is unavailable."
        ),
        created_at=now,
    )

    assert job.attempt_count == 0
    assert entry.submission_token == job.token
    assert entry.error_code == "handle_unavailable"
