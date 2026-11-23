import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.helpers.submission_store import LeaseLost, SubmissionStore
from app.models.submission import SubmissionJob

pytestmark = pytest.mark.postgres


def run(coro):
    """Run one async scenario."""
    return asyncio.run(coro)


CLAIM = {
    "lease_seconds": 300,
    "max_attempts": 3,
    "retry_base_seconds": 10,
    "retry_cap_seconds": 600,
}


def _maker(url: str):
    engine = create_async_engine(url, poolclass=NullPool)
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _create(
    maker,
    token: str,
    provider: str = "21.11155/A",
    fingerprint: dict | None = None,
):
    async with maker() as db:
        await SubmissionStore(db).create_queued_job(
            token=token,
            submitter_principal="SDK",
            provider_handle=provider,
            prefix="21.11155",
            issuer_profile={"has_issuer_name": "X", "has_issuer_id": "Y"},
            payload=[{"category": "avefi:WorkVariant"}],
            payload_digest="d" * 64,
            record_count=1,
            payload_bytes=100,
            validation_fingerprint=fingerprint,
        )


async def _claim(maker, worker_id: str):
    async with maker() as db:
        return await SubmissionStore(db).claim_job(
            worker_id=worker_id, **CLAIM
        )


async def _job(maker, token: str) -> SubmissionJob:
    async with maker() as db:
        return await db.get(SubmissionJob, token)


def test_claim_marks_oldest_job_running(postgres_url):
    async def scenario():
        engine, maker = _maker(postgres_url)
        try:
            await _create(maker, "job-1")
            job = await _claim(maker, "worker-1")

            assert job.token == "job-1"
            assert job.status == "running"
            assert job.worker_id == "worker-1"
            assert job.attempt_count == 1
            assert job.lease_expires_at is not None
            assert job.started_at is not None
        finally:
            await engine.dispose()

    run(scenario())


def test_create_persists_the_validation_fingerprint(postgres_url):
    async def scenario():
        engine, maker = _maker(postgres_url)
        try:
            fingerprint = {"package": "0.5.0", "version": "2.0"}
            await _create(maker, "job-1", fingerprint=fingerprint)

            job = await _job(maker, "job-1")

            assert job.validation_fingerprint == fingerprint
        finally:
            await engine.dispose()

    run(scenario())


def test_claim_skips_provider_with_running_job(postgres_url):
    async def scenario():
        engine, maker = _maker(postgres_url)
        try:
            await _create(maker, "job-1", "21.11155/A")
            await _create(maker, "job-2", "21.11155/B")
            await _create(maker, "job-3", "21.11155/A")

            first = await _claim(maker, "worker-1")
            second = await _claim(maker, "worker-2")
            third = await _claim(maker, "worker-3")

            assert first.token == "job-1"
            assert second.token == "job-2"
            assert third is None
        finally:
            await engine.dispose()

    run(scenario())


def test_expired_lease_is_requeued_with_backoff(postgres_url):
    async def scenario():
        engine, maker = _maker(postgres_url)
        try:
            await _create(maker, "job-1")
            await _claim(maker, "worker-1")
            async with maker() as db:
                await db.execute(
                    update(SubmissionJob)
                    .where(SubmissionJob.token == "job-1")
                    .values(
                        lease_expires_at=(
                            datetime.now(UTC) - timedelta(minutes=1)
                        ),
                        attempt_count=1,
                    )
                )
                await db.commit()

            claimed = await _claim(maker, "worker-2")
            job = await _job(maker, "job-1")

            assert claimed is None
            assert job.status == "queued"
            assert job.worker_id is None
            assert job.next_attempt_at is not None
            assert job.next_attempt_at > datetime.now(UTC)
        finally:
            await engine.dispose()

    run(scenario())


def test_expired_lease_with_exhausted_attempts_fails(postgres_url):
    async def scenario():
        engine, maker = _maker(postgres_url)
        try:
            await _create(maker, "job-1")
            await _claim(maker, "worker-1")
            async with maker() as db:
                await db.execute(
                    update(SubmissionJob)
                    .where(SubmissionJob.token == "job-1")
                    .values(
                        lease_expires_at=(
                            datetime.now(UTC) - timedelta(minutes=1)
                        ),
                        attempt_count=3,
                    )
                )
                await db.commit()

            claimed = await _claim(maker, "worker-2")
            job = await _job(maker, "job-1")

            assert claimed is None
            assert job.status == "failed"
            assert job.failure_code == "retry_exhausted"
            assert job.finished_at is not None
        finally:
            await engine.dispose()

    run(scenario())


def test_journal_append_is_fenced_by_worker_id(postgres_url):
    async def scenario():
        engine, maker = _maker(postgres_url)
        try:
            await _create(maker, "job-1")
            await _claim(maker, "worker-1")

            async with maker() as db:
                store = SubmissionStore(db)
                with pytest.raises(LeaseLost):
                    await store.append_journal(
                        "job-1",
                        worker_id="worker-2",
                        lease_seconds=300,
                        entry={"outcome": "succeeded", "action": "CREATE"},
                    )
                first = await store.append_journal(
                    "job-1",
                    worker_id="worker-1",
                    lease_seconds=300,
                    entry={"outcome": "succeeded", "action": "CREATE"},
                )
                second = await store.append_journal(
                    "job-1",
                    worker_id="worker-1",
                    lease_seconds=300,
                    entry={"outcome": "succeeded", "action": "UPDATE"},
                )
                entries = await store.get_all_journal_entries("job-1")

            assert (first, second) == (1, 2)
            assert [entry.sequence for entry in entries] == [1, 2]
        finally:
            await engine.dispose()

    run(scenario())


def test_running_provider_index_rejects_second_job(postgres_url):
    async def scenario():
        engine, maker = _maker(postgres_url)
        try:
            await _create(maker, "job-1", "21.11155/A")
            await _create(maker, "job-2", "21.11155/A")
            await _claim(maker, "worker-1")

            async with maker() as db:
                with pytest.raises(IntegrityError):
                    await db.execute(
                        update(SubmissionJob)
                        .where(SubmissionJob.token == "job-2")
                        .values(status="running")
                    )
                    await db.commit()
                await db.rollback()
        finally:
            await engine.dispose()

    run(scenario())


def test_claim_skips_locked_rows(postgres_url):
    async def scenario():
        engine, maker = _maker(postgres_url)
        try:
            await _create(maker, "job-1")
            async with maker() as holder:
                await holder.execute(
                    select(SubmissionJob)
                    .where(SubmissionJob.token == "job-1")
                    .with_for_update()
                )

                claimed = await _claim(maker, "worker-1")
                assert claimed is None
                await holder.rollback()

            claimed = await _claim(maker, "worker-1")
            assert claimed.token == "job-1"
        finally:
            await engine.dispose()

    run(scenario())


def test_concurrent_claims_run_only_one_job_per_provider(postgres_url):
    async def scenario():
        engine, maker = _maker(postgres_url)
        try:
            await _create(maker, "job-1", "21.11155/A")
            await _create(maker, "job-2", "21.11155/A")

            results = await asyncio.gather(
                _claim(maker, "worker-1"),
                _claim(maker, "worker-2"),
            )

            claimed = [job for job in results if job is not None]
            assert len(claimed) == 1
            job = await _job(maker, claimed[0].token)
            assert job.status == "running"
            assert job.worker_id in ("worker-1", "worker-2")
            assert job.worker_id == claimed[0].worker_id
        finally:
            await engine.dispose()

    run(scenario())


def test_pid_plan_is_persisted_and_reused(postgres_url):
    async def scenario():
        engine, maker = _maker(postgres_url)
        try:
            await _create(maker, "job-1")
            entry = (
                "avefi:LocalResource",
                "local-1",
                "21.11155/PLANNED",
                "local-1",
                "WorkVariant",
            )
            entry2 = (
                "avefi:LocalResource",
                "local-1",
                "21.11155/CHANGED",
                "local-1",
                "WorkVariant",
            )
            async with maker() as db:
                store = SubmissionStore(db)
                first = await store.ensure_pid_plan("job-1", [entry])
                second = await store.ensure_pid_plan("job-1", [entry2])

            key = ("avefi:LocalResource", "local-1")
            assert first[key] == "21.11155/PLANNED"
            assert second[key] == "21.11155/PLANNED"
        finally:
            await engine.dispose()

    run(scenario())
