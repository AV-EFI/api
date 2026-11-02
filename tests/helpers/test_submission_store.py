import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import settings
from app.helpers.submission_store import QueueLimitReached, SubmissionStore
from app.models.submission import SubmissionJob, SubmissionJournalEntry


def _run(coro):
    return asyncio.run(coro)


def _db():
    db = MagicMock()
    db.execute = AsyncMock()
    db.scalar = AsyncMock(return_value=0)
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


def _job_args(**overrides):
    args = {
        "token": "token-1",
        "submitter_principal": "SDK",
        "provider_handle": "21.11155/SDK",
        "prefix": "21.11155",
        "issuer_profile": {"has_issuer_name": "X", "has_issuer_id": "Y"},
        "payload": [{"category": "avefi:WorkVariant"}],
        "payload_digest": "d" * 64,
        "record_count": 1,
        "payload_bytes": 100,
    }
    args.update(overrides)
    return args


def test_create_queued_job_acquires_lock_and_inserts():
    db = _db()
    store = SubmissionStore(db)

    with patch.object(settings, "SUBMISSION_MAX_QUEUED_JOBS_PER_PROVIDER", 10):
        job = _run(store.create_queued_job(**_job_args()))

    assert isinstance(job, SubmissionJob)
    assert job.status == "queued"
    db.execute.assert_awaited_once()
    db.commit.assert_awaited_once()
    db.add.assert_called_once()


def test_create_queued_job_rejects_job_quota():
    db = _db()
    db.scalar.side_effect = [10, 500]
    store = SubmissionStore(db)

    with (
        patch.object(settings, "SUBMISSION_MAX_QUEUED_JOBS_PER_PROVIDER", 10),
        patch.object(
            settings, "SUBMISSION_MAX_QUEUED_BYTES_PER_PROVIDER", 100000
        ),
        pytest.raises(QueueLimitReached),
    ):
        _run(store.create_queued_job(**_job_args()))

    db.commit.assert_not_awaited()


def test_create_queued_job_rejects_byte_quota():
    db = _db()
    db.scalar.side_effect = [1, 1000]
    store = SubmissionStore(db)

    with (
        patch.object(settings, "SUBMISSION_MAX_QUEUED_JOBS_PER_PROVIDER", 10),
        patch.object(
            settings, "SUBMISSION_MAX_QUEUED_BYTES_PER_PROVIDER", 1000
        ),
        pytest.raises(QueueLimitReached),
    ):
        _run(store.create_queued_job(**_job_args()))

    db.commit.assert_not_awaited()


def test_get_job_returns_job():
    db = _db()
    job = _job_args()
    db.get = AsyncMock(return_value=job)
    store = SubmissionStore(db)

    result = _run(store.get_job("token-1"))

    assert result == job
    db.get.assert_awaited_once_with(SubmissionJob, "token-1")


def test_get_journal_counts():
    db = _db()
    db.scalar.side_effect = [3, 1]
    store = SubmissionStore(db)

    succeeded, failed = _run(store.get_journal_counts("token-1"))

    assert (succeeded, failed) == (3, 1)


def test_get_journal_returns_entries():
    db = _db()
    entry = SubmissionJournalEntry(
        submission_token="token-1",
        sequence=1,
        outcome="succeeded",
        created_at=datetime.now(UTC),
    )
    result = MagicMock()
    result.scalars.return_value = [entry]
    db.execute = AsyncMock(return_value=result)
    store = SubmissionStore(db)

    entries = _run(store.get_journal("token-1", after=0, limit=500))

    assert entries == [entry]
