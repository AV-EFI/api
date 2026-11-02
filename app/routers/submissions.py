import asyncio
import hashlib
import json
import logging
from typing import Annotated
import uuid

from avefi_schema import model_pydantic_v2 as efi
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.config import settings
from ..core.db import get_db
from ..helpers.submission_auth import (
    InvalidSubmissionCredentials,
    SubmissionAuthUnavailable,
    SubmissionIdentity,
    resolve_submission_identity,
)
from ..helpers.submission_store import QueueLimitReached, SubmissionStore
from ..models.submission import SubmissionJob
from ..schemas.submissions import (
    SubmissionAccepted,
    SubmissionJournalEntry,
    SubmissionJournalPage,
    SubmissionStatus,
)

log = logging.getLogger(__name__)
router = APIRouter()

_basic = HTTPBasic(auto_error=False)


def _deny() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Basic"},
    )


async def get_submission_identity(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(_basic)],
) -> SubmissionIdentity:
    """Resolve and authenticate a submission principal from Basic Auth."""
    if credentials is None:
        raise _deny()
    try:
        return await asyncio.to_thread(
            resolve_submission_identity,
            credentials.username,
            credentials.password,
        )
    except InvalidSubmissionCredentials:
        raise _deny() from None
    except SubmissionAuthUnavailable:
        raise HTTPException(
            status_code=503, detail="Service Unavailable"
        ) from None


Identity = Annotated[SubmissionIdentity, Depends(get_submission_identity)]
Session = Annotated[AsyncSession, Depends(get_db)]


def _validate_payload(data) -> int:
    """Validate submitted JSON and return the number of records."""
    if isinstance(data, list):
        efi.MovingImageRecords.model_validate(data)
        return len(data)
    efi.MovingImageRecordTypeAdapter.validate_python(data)
    return 1


def _store(db: AsyncSession) -> SubmissionStore:
    return SubmissionStore(db)


def _to_job_status(
    job: SubmissionJob, completed: int, failed: int
) -> SubmissionStatus:
    def ts(value) -> int | None:
        return int(value.timestamp()) if value else None

    return SubmissionStatus(
        token=job.token,
        status=job.status,
        record_count=job.record_count,
        completed_operations=completed,
        failed_operations=failed,
        created_at=ts(job.created_at),
        started_at=ts(job.started_at),
        finished_at=ts(job.finished_at),
        updated_at=ts(job.updated_at),
        failure_code=job.failure_code,
        failure_message=job.failure_message,
    )


@router.post(
    "",
    response_model=SubmissionAccepted,
    status_code=202,
    summary="Submit a chunk of AVefi records",
)
async def create_submission(
    identity: Identity,
    db: Session,
    request: Request,
):
    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > settings.SUBMISSION_MAX_BODY_BYTES:
                raise HTTPException(
                    status_code=413, detail="Payload Too Large"
                )
        except ValueError:
            pass

    raw = await request.body()
    if len(raw) > settings.SUBMISSION_MAX_BODY_BYTES:
        raise HTTPException(status_code=413, detail="Payload Too Large")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail="Invalid JSON") from None

    try:
        record_count = _validate_payload(data)
    except ValidationError:
        raise HTTPException(
            status_code=422, detail="Invalid AVefi records"
        ) from None

    if record_count > settings.SUBMISSION_MAX_RECORDS:
        raise HTTPException(
            status_code=422, detail="Record limit exceeded"
        ) from None

    store = _store(db)
    token = str(uuid.uuid4())
    try:
        await store.create_queued_job(
            token=token,
            submitter_principal=identity.submitter_principal,
            provider_handle=identity.provider_handle,
            prefix=identity.prefix,
            issuer_profile=identity.profile,
            payload=data,
            payload_digest=hashlib.sha256(raw).hexdigest(),
            record_count=record_count,
            payload_bytes=len(raw),
        )
    except QueueLimitReached:
        raise HTTPException(
            status_code=409, detail="Provider queue limit reached"
        ) from None

    return SubmissionAccepted(
        token=token,
        status="queued",
        status_url=f"/rest/v1/submissions/{token}",
    )


async def _authorized_job(
    store: SubmissionStore, token: str, identity: SubmissionIdentity
) -> SubmissionJob:
    job = await store.get_job(token)
    if job is None:
        raise HTTPException(status_code=404, detail="Not found")
    if (
        job.authentication_method != "basic"
        or job.submitter_principal != identity.submitter_principal
    ):
        raise _deny()
    return job


@router.get(
    "/{token}",
    response_model=SubmissionStatus,
    summary="Read submission status",
)
async def submission_status(
    token: str,
    identity: Identity,
    db: Session,
):
    store = _store(db)
    job = await _authorized_job(store, token, identity)
    completed, failed = await store.get_journal_counts(token)
    return _to_job_status(job, completed, failed)


@router.get(
    "/{token}/journal",
    response_model=SubmissionJournalPage,
    summary="Read the submission journal with cursor pagination",
)
async def submission_journal(
    token: str,
    identity: Identity,
    db: Session,
    after: int = 0,
    limit: int = settings.SUBMISSION_JOURNAL_PAGE_SIZE,
):
    store = _store(db)
    await _authorized_job(store, token, identity)
    page_size = max(1, min(limit, settings.SUBMISSION_JOURNAL_PAGE_SIZE))
    entries = await store.get_journal(token, after=after, limit=page_size)

    def ts(value) -> int | None:
        return int(value.timestamp()) if value else None

    return SubmissionJournalPage(
        entries=[
            SubmissionJournalEntry(
                sequence=entry.sequence,
                outcome=entry.outcome,
                action=entry.action,
                pid=entry.pid,
                local_id=entry.local_id,
                record_type=entry.record_type,
                error_code=entry.error_code,
                error_message=entry.error_message,
                created_at=ts(entry.created_at),
            )
            for entry in entries
        ],
        next_after=(
            entries[-1].sequence if len(entries) == page_size else None
        ),
    )
