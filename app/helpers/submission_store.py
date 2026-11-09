from datetime import UTC, datetime, timedelta
import logging
import zlib

from sqlalchemy import func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import settings
from app.models.submission import (
    SubmissionJob,
    SubmissionJournalEntry,
    SubmissionPidPlan,
)

log = logging.getLogger(__name__)


class QueueLimitReached(Exception):
    """The provider queue quota would be exceeded by this submission."""


class LeaseLost(Exception):
    """The worker no longer owns the job lease."""


def _provider_lock_key(provider_handle: str) -> int:
    """Return a stable PostgreSQL advisory lock key for a provider handle."""
    return zlib.crc32(provider_handle.encode("utf-8"))


class SubmissionStore:
    """Durable job and journal access for submissions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_queued_job(
        self,
        *,
        token: str,
        submitter_principal: str,
        provider_handle: str,
        prefix: str,
        issuer_profile: dict[str, str],
        payload: dict | list,
        payload_digest: str,
        record_count: int,
        payload_bytes: int,
    ) -> SubmissionJob:
        """Atomically enforce provider queue quotas and insert a queued job.

        A PostgreSQL advisory transaction lock serializes admission for the
        same provider, so concurrent submissions cannot both exceed a quota.
        """
        await self.db.execute(
            text("SELECT pg_advisory_xact_lock(:key)"),
            {"key": _provider_lock_key(provider_handle)},
        )

        queued_count = await self.db.scalar(
            select(func.count())
            .select_from(SubmissionJob)
            .where(
                SubmissionJob.provider_handle == provider_handle,
                SubmissionJob.status == "queued",
            )
        )
        queued_bytes = await self.db.scalar(
            select(func.coalesce(func.sum(SubmissionJob.payload_bytes), 0))
            .select_from(SubmissionJob)
            .where(
                SubmissionJob.provider_handle == provider_handle,
                SubmissionJob.status == "queued",
            )
        )

        if queued_count >= settings.SUBMISSION_MAX_QUEUED_JOBS_PER_PROVIDER:
            raise QueueLimitReached("jobs")
        if queued_bytes + payload_bytes > (
            settings.SUBMISSION_MAX_QUEUED_BYTES_PER_PROVIDER
        ):
            raise QueueLimitReached("bytes")

        job = SubmissionJob(
            token=token,
            submitter_principal=submitter_principal,
            authentication_method="basic",
            provider_handle=provider_handle,
            prefix=prefix,
            issuer_profile=issuer_profile,
            payload=payload,
            payload_digest=payload_digest,
            record_count=record_count,
            payload_bytes=payload_bytes,
            status="queued",
        )
        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)
        return job

    async def get_job(self, token: str) -> SubmissionJob | None:
        """Return a job by token, or None if it does not exist."""
        return await self.db.get(SubmissionJob, token)

    async def get_journal_counts(self, token: str) -> tuple[int, int]:
        """Return (succeeded, failed) journal operation counts for a job."""
        succeeded = await self.db.scalar(
            select(func.count())
            .select_from(SubmissionJournalEntry)
            .where(
                SubmissionJournalEntry.submission_token == token,
                SubmissionJournalEntry.outcome == "succeeded",
            )
        )
        failed = await self.db.scalar(
            select(func.count())
            .select_from(SubmissionJournalEntry)
            .where(
                SubmissionJournalEntry.submission_token == token,
                SubmissionJournalEntry.outcome == "failed",
            )
        )
        return succeeded or 0, failed or 0

    async def get_journal(
        self,
        token: str,
        *,
        after: int,
        limit: int,
    ) -> list[SubmissionJournalEntry]:
        """Return journal entries after ``after`` in sequence order."""
        stmt = (
            select(SubmissionJournalEntry)
            .where(
                SubmissionJournalEntry.submission_token == token,
                SubmissionJournalEntry.sequence > after,
            )
            .order_by(SubmissionJournalEntry.sequence)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars())

    async def get_all_journal_entries(
        self, token: str
    ) -> list[SubmissionJournalEntry]:
        """Return every journal entry for a job in sequence order."""
        stmt = (
            select(SubmissionJournalEntry)
            .where(SubmissionJournalEntry.submission_token == token)
            .order_by(SubmissionJournalEntry.sequence)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars())

    async def claim_job(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        max_attempts: int,
        retry_base_seconds: int,
        retry_cap_seconds: int,
    ) -> SubmissionJob | None:
        """Claim the oldest eligible job whose provider is idle.

        Expired running jobs are first requeued with backoff or failed when
        their attempt budget is exhausted.
        """
        now = datetime.now(UTC)
        await self._reap_stale_jobs(
            now=now,
            max_attempts=max_attempts,
            retry_base_seconds=retry_base_seconds,
            retry_cap_seconds=retry_cap_seconds,
        )

        stmt = _eligible_job_stmt(now)
        job = (await self.db.execute(stmt)).scalar_one_or_none()
        if job is None:
            await self.db.commit()
            return None

        job.status = "running"
        job.worker_id = worker_id
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.attempt_count = (job.attempt_count or 0) + 1
        job.started_at = job.started_at or now
        job.updated_at = now
        job.next_attempt_at = None
        try:
            await self.db.commit()
        except IntegrityError:
            # Another worker claimed a job for this provider between our
            # selection and commit; the partial unique index rejected it.
            await self.db.rollback()
            return None
        await self.db.refresh(job)
        return job

    async def _reap_stale_jobs(
        self,
        *,
        now: datetime,
        max_attempts: int,
        retry_base_seconds: int,
        retry_cap_seconds: int,
    ) -> None:
        stale = (await self.db.execute(_stale_job_stmt(now))).scalars().all()
        for job in stale:
            job.worker_id = None
            job.lease_expires_at = None
            job.updated_at = now
            if (job.attempt_count or 0) >= max_attempts:
                job.status = "failed"
                job.failure_code = "retry_exhausted"
                job.failure_message = "Retry limit reached after lease expiry"
                job.finished_at = now
                job.next_attempt_at = None
            else:
                job.status = "queued"
                job.next_attempt_at = now + timedelta(
                    seconds=_retry_delay(
                        job.attempt_count,
                        retry_base_seconds,
                        retry_cap_seconds,
                    )
                )

    async def extend_lease(
        self,
        token: str,
        *,
        worker_id: str,
        lease_seconds: int,
    ) -> bool:
        """Extend a running job's lease if ``worker_id`` still owns it."""
        now = datetime.now(UTC)
        result = await self.db.execute(
            update(SubmissionJob)
            .where(
                SubmissionJob.token == token,
                SubmissionJob.status == "running",
                SubmissionJob.worker_id == worker_id,
                SubmissionJob.lease_expires_at.is_not(None),
                SubmissionJob.lease_expires_at > now,
            )
            .values(
                lease_expires_at=now + timedelta(seconds=lease_seconds),
                updated_at=now,
            )
        )
        await self.db.commit()
        return (result.rowcount or 0) > 0

    async def append_journal(
        self,
        token: str,
        *,
        worker_id: str,
        lease_seconds: int,
        entry: dict,
    ) -> int:
        """Append one checkpoint after verifying job ownership."""
        now = datetime.now(UTC)
        job = await self._locked_job(token)
        _assert_owner(job, worker_id, now)

        next_sequence = await self.db.scalar(
            select(
                func.coalesce(func.max(SubmissionJournalEntry.sequence), 0) + 1
            ).where(SubmissionJournalEntry.submission_token == token)
        )
        row = SubmissionJournalEntry(
            submission_token=token,
            sequence=next_sequence,
            outcome=entry.get("outcome", "succeeded"),
            action=entry.get("action"),
            pid=entry.get("pid"),
            local_id=entry.get("local_id"),
            record_type=entry.get("record_type"),
            error_code=entry.get("error_code"),
            error_message=entry.get("error_message"),
        )
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.updated_at = now
        self.db.add(row)
        await self.db.commit()
        return next_sequence

    async def requeue_job(
        self,
        token: str,
        *,
        worker_id: str,
        failure_code: str,
        failure_message: str,
        max_attempts: int,
        retry_base_seconds: int,
        retry_cap_seconds: int,
    ) -> str:
        """Requeue a retryable failure or mark it failed when exhausted."""
        now = datetime.now(UTC)
        job = await self._locked_job(token)
        _assert_owner(job, worker_id, now)
        job.worker_id = None
        job.lease_expires_at = None
        job.updated_at = now
        if (job.attempt_count or 0) >= max_attempts:
            job.status = "failed"
            job.failure_code = "retry_exhausted"
            job.failure_message = (
                f"Retry limit reached after {job.attempt_count} attempts"
                f" (last error: {failure_code})"
            )
            job.finished_at = now
            job.next_attempt_at = None
            status = "failed"
        else:
            job.status = "queued"
            job.next_attempt_at = now + timedelta(
                seconds=_retry_delay(
                    job.attempt_count,
                    retry_base_seconds,
                    retry_cap_seconds,
                )
            )
            status = "queued"
        await self.db.commit()
        return status

    async def finalize_job(
        self,
        token: str,
        *,
        worker_id: str,
        status: str,
        failure_code: str | None = None,
        failure_message: str | None = None,
    ) -> None:
        """Mark a job terminal after verifying job ownership."""
        now = datetime.now(UTC)
        job = await self._locked_job(token)
        _assert_owner(job, worker_id, now)
        job.status = status
        job.finished_at = now
        job.worker_id = None
        job.lease_expires_at = None
        job.next_attempt_at = None
        job.updated_at = now
        job.failure_code = failure_code
        job.failure_message = failure_message
        await self.db.commit()

    async def get_pid_plan(self, token: str) -> dict[tuple[str, str], str]:
        """Return the persisted PID plan for a job."""
        rows = (
            await self.db.execute(
                select(SubmissionPidPlan).where(
                    SubmissionPidPlan.submission_token == token
                )
            )
        ).scalars()
        return {
            (row.identifier_category, row.identifier_id): row.planned_pid
            for row in rows
        }

    async def ensure_pid_plan(
        self,
        token: str,
        entries: list[tuple[str, str, str, str | None, str | None]],
        *,
        worker_id: str | None = None,
    ) -> dict[tuple[str, str], str]:
        """Insert missing PID plan entries and return the complete plan.

        Insertion is idempotent, so a retry that overlaps with a stale
        worker cannot replace an already assigned PID.
        """
        if worker_id is not None:
            now = datetime.now(UTC)
            job = await self._locked_job(token)
            _assert_owner(job, worker_id, now)

        if entries:
            created_at = datetime.now(UTC)
            await self.db.execute(
                insert(SubmissionPidPlan)
                .values(
                    [
                        {
                            "submission_token": token,
                            "identifier_category": category,
                            "identifier_id": identifier,
                            "planned_pid": pid,
                            "local_id": local_id,
                            "record_type": record_type,
                            "created_at": created_at,
                        }
                        for (
                            category,
                            identifier,
                            pid,
                            local_id,
                            record_type,
                        ) in entries
                    ]
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        "submission_token",
                        "identifier_category",
                        "identifier_id",
                    ]
                )
            )
        await self.db.commit()
        return await self.get_pid_plan(token)

    async def _locked_job(self, token: str) -> SubmissionJob | None:
        stmt = (
            select(SubmissionJob)
            .where(SubmissionJob.token == token)
            .with_for_update()
        )
        return (await self.db.execute(stmt)).scalar_one_or_none()


def _stale_job_stmt(now: datetime):
    return (
        select(SubmissionJob)
        .where(
            SubmissionJob.status == "running",
            SubmissionJob.lease_expires_at.is_not(None),
            SubmissionJob.lease_expires_at < now,
        )
        .with_for_update(skip_locked=True)
    )


def _eligible_job_stmt(now: datetime):
    running = aliased(SubmissionJob)
    blocked = (
        select(running.token)
        .where(
            running.provider_handle == SubmissionJob.provider_handle,
            running.status == "running",
        )
        .exists()
    )
    return (
        select(SubmissionJob)
        .where(
            SubmissionJob.status == "queued",
            or_(
                SubmissionJob.next_attempt_at.is_(None),
                SubmissionJob.next_attempt_at <= now,
            ),
            ~blocked,
        )
        .order_by(SubmissionJob.created_at, SubmissionJob.token)
        .with_for_update(skip_locked=True)
        .limit(1)
    )


def _assert_owner(
    job: SubmissionJob | None, worker_id: str, now: datetime
) -> None:
    if (
        job is None
        or job.status != "running"
        or job.worker_id != worker_id
        or job.lease_expires_at is None
        or job.lease_expires_at <= now
    ):
        raise LeaseLost


def _retry_delay(
    attempt_count: int | None, base_seconds: int, cap_seconds: int
) -> int:
    exponent = max((attempt_count or 0) - 1, 0)
    return min(base_seconds * (2**exponent), cap_seconds)
