import logging
import zlib

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.submission import SubmissionJob, SubmissionJournalEntry

log = logging.getLogger(__name__)


class QueueLimitReached(Exception):
    """The provider queue quota would be exceeded by this submission."""


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
