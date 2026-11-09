import asyncio
import contextlib
import logging
import os
import socket
from typing import Any
from uuid import uuid4

import httpx2
from pydantic import ValidationError

from .core.config import HandleConfigError, settings
from .core.db import get_async_session_maker
from .helpers.epic_client import create_service_client
from .helpers.submission_payload import decode_payload
from .helpers.submission_store import LeaseLost, SubmissionStore
from .helpers.task_manager import (
    CheckpointAborted,
    Scheduler,
    SchedulerTaskError,
    UnreferencedError,
)
from .models.submission import SubmissionJournalEntry

log = logging.getLogger(__name__)


def _session_factory():
    return get_async_session_maker()()


def _run_on_loop(loop: asyncio.AbstractEventLoop, coro):
    return asyncio.run_coroutine_threadsafe(coro, loop).result()


def _worker_id() -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"


def _classify(exc: BaseException) -> tuple[str, str, bool]:
    """Return (error_code, safe_message, retryable) for ``exc``."""
    if isinstance(exc, SchedulerTaskError):
        return _classify(exc.cause)
    if isinstance(exc, HandleConfigError):
        return (
            "service_credentials_unavailable",
            "Server-side Handle credentials are unavailable",
            False,
        )
    if isinstance(exc, httpx2.HTTPStatusError):
        status = exc.response.status_code
        if status in (401, 403):
            return ("auth_failed", "Handle authentication failed", False)
        if status == 404:
            return ("remote_not_found", "Remote record was not found", False)
        if status in (408, 429) or status >= 500:
            return (
                "dependency_unavailable",
                "Handle service is unavailable",
                True,
            )
        return ("remote_error", "Handle request was rejected", False)
    if isinstance(exc, (httpx2.TransportError, httpx2.TimeoutException)):
        return (
            "dependency_unavailable",
            "Handle service is unavailable",
            True,
        )
    if isinstance(exc, (UnreferencedError, ValidationError, ValueError)):
        return ("invalid_payload", "Submission payload is invalid", False)
    return ("internal_error", "Submission processing failed", False)


def _scheduler_classifier(exc: BaseException) -> tuple[str, str]:
    code, message, _ = _classify(exc)
    return code, message


def _journal_entry(
    row: SubmissionJournalEntry,
) -> dict[str, Any]:
    """Return a result-log entry for a completed journal row."""
    return {
        "action": row.action,
        "pid": row.pid,
        "local_id": row.local_id,
        "record_type": row.record_type,
    }


class _Checkpoint:
    """Persist scheduler checkpoints through the async store."""

    def __init__(
        self, loop: asyncio.AbstractEventLoop, token: str, worker_id: str
    ):
        self.loop = loop
        self.token = token
        self.worker_id = worker_id

    def __call__(self, entry: dict) -> None:
        try:
            _run_on_loop(self.loop, self._append(entry))
        except LeaseLost as exc:
            raise CheckpointAborted from exc

    def before_task(self, task) -> None:
        """Verify and extend the lease immediately before a remote call."""
        try:
            extended = _run_on_loop(self.loop, self._extend())
        except LeaseLost as exc:
            raise CheckpointAborted from exc
        if not extended:
            raise CheckpointAborted

    async def _append(self, entry: dict) -> None:
        async with _session_factory() as db:
            await SubmissionStore(db).append_journal(
                self.token,
                worker_id=self.worker_id,
                lease_seconds=settings.SUBMISSION_WORKER_LEASE_SECONDS,
                entry=entry,
            )

    async def _extend(self) -> bool:
        async with _session_factory() as db:
            return await SubmissionStore(db).extend_lease(
                self.token,
                worker_id=self.worker_id,
                lease_seconds=settings.SUBMISSION_WORKER_LEASE_SECONDS,
            )


async def _get_journal(token: str) -> list[dict[str, Any]]:
    async with _session_factory() as db:
        rows = await SubmissionStore(db).get_all_journal_entries(token)
        return [
            _journal_entry(row) for row in rows if row.outcome == "succeeded"
        ]


async def _ensure_plan(
    token: str,
    entries: list[tuple[str, str, str, str | None, str | None]],
    worker_id: str,
) -> dict[tuple[str, str], str]:
    async with _session_factory() as db:
        return await SubmissionStore(db).ensure_pid_plan(
            token, entries, worker_id=worker_id
        )


async def _finalize(
    token: str,
    worker_id: str,
    status: str,
    failure_code: str | None = None,
    failure_message: str | None = None,
) -> None:
    async with _session_factory() as db:
        await SubmissionStore(db).finalize_job(
            token,
            worker_id=worker_id,
            status=status,
            failure_code=failure_code,
            failure_message=failure_message,
        )


async def _requeue(
    token: str,
    worker_id: str,
    failure_code: str,
    failure_message: str,
) -> str:
    async with _session_factory() as db:
        return await SubmissionStore(db).requeue_job(
            token,
            worker_id=worker_id,
            failure_code=failure_code,
            failure_message=failure_message,
            max_attempts=settings.SUBMISSION_WORKER_MAX_ATTEMPTS,
            retry_base_seconds=(settings.SUBMISSION_WORKER_RETRY_BASE_SECONDS),
            retry_cap_seconds=(settings.SUBMISSION_WORKER_RETRY_MAX_SECONDS),
        )


def _plan_entries(
    scheduler: Scheduler, prefix: str
) -> list[tuple[str, str, str, str | None, str | None]]:
    entries = []
    for handler in scheduler.pending_create_handlers():
        planned_pid = f"{prefix}/{uuid4().hex.upper()}"
        entries.append(
            (
                handler.name[0],
                handler.name[1],
                planned_pid,
                handler.local_id,
                (
                    type(handler.record).__name__
                    if handler.record is not None
                    else None
                ),
            )
        )
    return entries


def _run_job(job: dict[str, Any], loop: asyncio.AbstractEventLoop) -> None:
    token = job["token"]
    worker_id = job["worker_id"]
    checkpoint = _Checkpoint(loop, token, worker_id)

    try:
        with create_service_client(
            profile=job["issuer_profile"], prefix=job["prefix"]
        ) as client:
            records = decode_payload(job["payload"])
            result_log = _run_on_loop(loop, _get_journal(token))
            scheduler = Scheduler(
                client,
                result_log,
                checkpoint=checkpoint,
                before_task=checkpoint.before_task,
                error_classifier=_scheduler_classifier,
            )
            for record in records:
                scheduler.add_record(record)

            scheduler.record_reverse_dependencies()
            scheduler.skip_previously_logged_tasks()
            graph = scheduler.prepare_dependency_graph()
            plan_entries = _plan_entries(scheduler, job["prefix"])
            plan = _run_on_loop(
                loop, _ensure_plan(token, plan_entries, worker_id)
            )
            scheduler.apply_planned_pids(plan)
            scheduler.execute_graph(graph)
    except CheckpointAborted:
        log.warning("Lost lease for submission %s; stopping", token)
        return
    except LeaseLost:
        log.warning("Lost lease for submission %s; stopping", token)
        return
    except Exception as exc:
        code, message, retryable = _classify(exc)
        log.exception("Submission %s failed with %s", token, code)
        if not isinstance(exc, SchedulerTaskError):
            _record_planning_failure(checkpoint, code, message)
        try:
            if retryable:
                _run_on_loop(loop, _requeue(token, worker_id, code, message))
            else:
                _run_on_loop(
                    loop,
                    _finalize(
                        token,
                        worker_id,
                        "failed",
                        failure_code=code,
                        failure_message=message,
                    ),
                )
        except LeaseLost:
            log.warning("Lost lease while finalizing submission %s", token)
        return

    try:
        _run_on_loop(loop, _finalize(token, worker_id, "succeeded"))
    except LeaseLost:
        log.warning("Lost lease while finalizing submission %s", token)


def _record_planning_failure(
    checkpoint: _Checkpoint, code: str, message: str
) -> None:
    with contextlib.suppress(CheckpointAborted):
        checkpoint(
            {
                "outcome": "failed",
                "action": None,
                "error_code": code,
                "error_message": message,
            }
        )


async def _claim(worker_id: str) -> dict[str, Any] | None:
    async with _session_factory() as db:
        job = await SubmissionStore(db).claim_job(
            worker_id=worker_id,
            lease_seconds=settings.SUBMISSION_WORKER_LEASE_SECONDS,
            max_attempts=settings.SUBMISSION_WORKER_MAX_ATTEMPTS,
            retry_base_seconds=(settings.SUBMISSION_WORKER_RETRY_BASE_SECONDS),
            retry_cap_seconds=(settings.SUBMISSION_WORKER_RETRY_MAX_SECONDS),
        )
        if job is None:
            return None
        return {
            "token": job.token,
            "worker_id": worker_id,
            "prefix": job.prefix,
            "issuer_profile": job.issuer_profile,
            "payload": job.payload,
        }


async def run_worker() -> None:
    """Poll for and process one submission job at a time."""
    worker_id = _worker_id()
    log.info("Submission worker started: %s", worker_id)
    while True:
        job = await _claim(worker_id)
        if job is None:
            await asyncio.sleep(settings.SUBMISSION_WORKER_POLL_SECONDS)
            continue
        loop = asyncio.get_running_loop()
        try:
            await asyncio.to_thread(_run_job, job, loop)
        except Exception:
            log.exception(
                "Unexpected worker failure for submission %s",
                job["token"],
            )


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        log.info("Submission worker stopped")


if __name__ == "__main__":
    main()
