from types import SimpleNamespace

from httpx2 import ConnectError, HTTPStatusError, Request, Response
from pydantic import ValidationError

from app.core.config import HandlePrefixNotConfigured
from app.helpers.task_manager import Operation, SchedulerTaskError
from app.worker import _classify, _plan_entries


def _status_error(status: int) -> HTTPStatusError:
    request = Request("PUT", "https://handles.example/pid")
    response = Response(status, request=request)
    return HTTPStatusError("failed", request=request, response=response)


def _task_error(cause: BaseException) -> SchedulerTaskError:
    handler = SimpleNamespace(
        local_id="local-1",
        pid="21.11155/PID",
        name=("avefi:LocalResource", "local-1"),
        record=object(),
    )
    task = SimpleNamespace(
        operation=Operation.CREATE,
        handler=handler,
    )
    return SchedulerTaskError(task, cause)


def test_classify_authentication_failure_is_terminal():
    assert _classify(_status_error(401)) == (
        "auth_failed",
        "Handle authentication failed",
        False,
    )


def test_classify_upstream_failure_is_retryable():
    assert _classify(_status_error(503)) == (
        "dependency_unavailable",
        "Handle service is unavailable",
        True,
    )


def test_classify_transport_failure_is_retryable():
    code, message, retryable = _classify(ConnectError("down"))

    assert code == "dependency_unavailable"
    assert retryable is True
    assert message == "Handle service is unavailable"


def test_classify_unwraps_scheduler_task_error():
    classified = _classify(_task_error(_status_error(503)))

    assert classified == (
        "dependency_unavailable",
        "Handle service is unavailable",
        True,
    )


def test_classify_missing_credentials_is_terminal():
    classified = _classify(HandlePrefixNotConfigured("21.11155"))

    assert classified == (
        "service_credentials_unavailable",
        "Server-side Handle credentials are unavailable",
        False,
    )


def test_classify_validation_failure_is_terminal():
    code, _, retryable = _classify(
        ValidationError.from_exception_data("Model", [])
    )

    assert code == "invalid_payload"
    assert retryable is False


def test_classify_unknown_failure_is_internal():
    code, _, retryable = _classify(RuntimeError("boom"))

    assert code == "internal_error"
    assert retryable is False


class _Handler:
    name = ("avefi:LocalResource", "local-1")
    local_id = "local-1"
    record = object()


class _Scheduler:
    def pending_create_handlers(self):
        return [_Handler()]


def test_plan_entries_use_prefix_and_stable_record_key():
    entries = _plan_entries(_Scheduler(), "21.11155")

    assert len(entries) == 1
    category, identifier, pid, local_id, record_type = entries[0]
    assert (category, identifier) == (
        "avefi:LocalResource",
        "local-1",
    )
    assert pid.startswith("21.11155/")
    assert local_id == "local-1"
    assert record_type == "object"
