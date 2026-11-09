from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
import pytest

from app.core.config import settings
from app.core.db import get_db
from app.helpers.submission_auth import (
    InvalidSubmissionCredentials,
    SubmissionAuthUnavailable,
    SubmissionIdentity,
)
from app.helpers.submission_store import QueueLimitReached
from app.main import EFI_PATH, api
from app.main import app as main_app
from app.models.submission import SubmissionJob, SubmissionJournalEntry

client = TestClient(main_app)


def _identity():
    return SubmissionIdentity(
        submitter_principal="SDK",
        authentication_method="basic",
        provider_handle="21.11155/SDK",
        prefix="21.11155",
        profile={
            "has_issuer_name": "Stiftung Deutsche Kinemathek",
            "has_issuer_id": "https://w3id.org/isil/DE-MUS-407010",
        },
    )


def _job(token="token-1", submitter="SDK"):
    now = datetime.now(UTC)
    return SubmissionJob(
        token=token,
        submitter_principal=submitter,
        authentication_method="basic",
        provider_handle="21.11155/SDK",
        prefix="21.11155",
        issuer_profile={"has_issuer_name": "X", "has_issuer_id": "Y"},
        payload=[{"category": "avefi:WorkVariant"}],
        payload_digest="d" * 64,
        record_count=1,
        payload_bytes=100,
        status="queued",
        created_at=now,
        updated_at=now,
    )


def _entry(sequence=1, outcome="succeeded"):
    return SubmissionJournalEntry(
        submission_token="token-1",
        sequence=sequence,
        outcome=outcome,
        action="CREATE",
        pid="21.11155/ABC",
        created_at=datetime.now(UTC),
    )


def _store(**overrides):
    store = MagicMock()
    store.create_queued_job = AsyncMock(return_value=_job())
    store.get_job = AsyncMock(return_value=_job())
    store.get_journal_counts = AsyncMock(return_value=(1, 0))
    store.get_journal = AsyncMock(return_value=[])
    for key, value in overrides.items():
        setattr(store, key, value)
    return store


@pytest.fixture
def api_client():
    async def _fake_db():
        yield MagicMock()

    api.dependency_overrides[get_db] = _fake_db
    yield client
    api.dependency_overrides.pop(get_db, None)


def _valid_record():
    return {
        "category": "avefi:WorkVariant",
        "has_primary_title": {"has_name": "Test", "type": "PreferredTitle"},
        "type": "Monographic",
    }


@pytest.fixture
def auth_identity():
    with patch(
        "app.routers.submissions.resolve_submission_identity",
        return_value=_identity(),
    ):
        yield


@pytest.fixture
def service_credentials_ok():
    with patch("app.routers.submissions.require_service_credentials"):
        yield


def test_missing_basic_auth_returns_401(api_client):
    response = api_client.post(f"{EFI_PATH}/submissions", json=_valid_record())
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Basic"


def test_invalid_credentials_return_401(api_client):
    with patch(
        "app.routers.submissions.resolve_submission_identity",
        side_effect=InvalidSubmissionCredentials,
    ):
        response = api_client.post(
            f"{EFI_PATH}/submissions",
            json=_valid_record(),
            auth=("SDK", "wrong"),
        )
    assert response.status_code == 401


def test_auth_unavailable_returns_503(api_client):
    with patch(
        "app.routers.submissions.resolve_submission_identity",
        side_effect=SubmissionAuthUnavailable,
    ):
        response = api_client.post(
            f"{EFI_PATH}/submissions",
            json=_valid_record(),
            auth=("SDK", "password"),
        )
    assert response.status_code == 503


def test_oversized_body_returns_413(
    api_client, auth_identity, service_credentials_ok
):
    with patch.object(settings, "SUBMISSION_MAX_BODY_BYTES", 100):
        response = api_client.post(
            f"{EFI_PATH}/submissions",
            content=b'{"x": "' + b"a" * 200 + b'"}',
            headers={"content-type": "application/json"},
            auth=("SDK", "password"),
        )
    assert response.status_code == 413


def test_invalid_json_returns_422(
    api_client, auth_identity, service_credentials_ok
):
    with patch("app.routers.submissions.SubmissionStore"):
        response = api_client.post(
            f"{EFI_PATH}/submissions",
            content=b"not json",
            headers={"content-type": "application/json"},
            auth=("SDK", "password"),
        )
    assert response.status_code == 422


def test_schema_invalid_returns_422(
    api_client, auth_identity, service_credentials_ok
):
    with patch("app.routers.submissions.SubmissionStore"):
        response = api_client.post(
            f"{EFI_PATH}/submissions",
            json={"category": "avefi:WorkVariant", "type": "Monographic"},
            auth=("SDK", "password"),
        )
    assert response.status_code == 422


def test_record_count_limit_returns_422(
    api_client, auth_identity, service_credentials_ok
):
    records = [_valid_record(), _valid_record()]
    with (
        patch("app.routers.submissions.SubmissionStore"),
        patch.object(settings, "SUBMISSION_MAX_RECORDS", 1),
    ):
        response = api_client.post(
            f"{EFI_PATH}/submissions", json=records, auth=("SDK", "password")
        )
    assert response.status_code == 422


def test_create_single_record_returns_202(
    api_client, auth_identity, service_credentials_ok
):
    store = _store()
    with patch("app.routers.submissions.SubmissionStore", return_value=store):
        response = api_client.post(
            f"{EFI_PATH}/submissions",
            json=_valid_record(),
            auth=("SDK", "password"),
        )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["status_url"].startswith("/rest/v1/submissions/")
    store.create_queued_job.assert_awaited_once()


def test_create_queue_limit_returns_409(
    api_client, auth_identity, service_credentials_ok
):
    store = _store()
    store.create_queued_job = AsyncMock(side_effect=QueueLimitReached("jobs"))
    with patch("app.routers.submissions.SubmissionStore", return_value=store):
        response = api_client.post(
            f"{EFI_PATH}/submissions",
            json=_valid_record(),
            auth=("SDK", "password"),
        )
    assert response.status_code == 409


def test_server_credentials_missing_returns_503(api_client, auth_identity):
    store = _store()
    with (
        patch(
            "app.routers.submissions.require_service_credentials",
            side_effect=SubmissionAuthUnavailable,
        ),
        patch("app.routers.submissions.SubmissionStore", return_value=store),
    ):
        response = api_client.post(
            f"{EFI_PATH}/submissions",
            json=_valid_record(),
            auth=("SDK", "password"),
        )

    assert response.status_code == 503
    store.create_queued_job.assert_not_awaited()


def test_status_does_not_require_server_credentials(api_client, auth_identity):
    store = _store()
    with (
        patch(
            "app.routers.submissions.require_service_credentials"
        ) as require_credentials,
        patch("app.routers.submissions.SubmissionStore", return_value=store),
    ):
        response = api_client.get(
            f"{EFI_PATH}/submissions/token-1", auth=("SDK", "password")
        )

    assert response.status_code == 200
    require_credentials.assert_not_called()


def test_status_returns_compact_summary(api_client, auth_identity):
    store = _store()
    with patch("app.routers.submissions.SubmissionStore", return_value=store):
        response = api_client.get(
            f"{EFI_PATH}/submissions/token-1", auth=("SDK", "password")
        )
    assert response.status_code == 200
    body = response.json()
    assert body["token"] == "token-1"
    assert body["status"] == "queued"
    assert body["record_count"] == 1
    assert body["completed_operations"] == 1


def test_status_unknown_token_returns_404(api_client, auth_identity):
    store = _store(get_job=AsyncMock(return_value=None))
    with patch("app.routers.submissions.SubmissionStore", return_value=store):
        response = api_client.get(
            f"{EFI_PATH}/submissions/missing", auth=("SDK", "password")
        )
    assert response.status_code == 404


def test_status_wrong_principal_returns_401(api_client, auth_identity):
    store = _store(get_job=AsyncMock(return_value=_job(submitter="other")))
    with patch("app.routers.submissions.SubmissionStore", return_value=store):
        response = api_client.get(
            f"{EFI_PATH}/submissions/token-1", auth=("SDK", "password")
        )
    assert response.status_code == 401


def test_journal_paginates_entries(api_client, auth_identity):
    store = _store(
        get_job=AsyncMock(return_value=_job()),
        get_journal=AsyncMock(return_value=[_entry(1), _entry(2)]),
    )
    with patch("app.routers.submissions.SubmissionStore", return_value=store):
        response = api_client.get(
            f"{EFI_PATH}/submissions/token-1/journal",
            params={"limit": 100},
            auth=("SDK", "password"),
        )
    assert response.status_code == 200
    body = response.json()
    assert len(body["entries"]) == 2
    assert body["entries"][0]["sequence"] == 1
