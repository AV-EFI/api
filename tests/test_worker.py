import asyncio
import inspect
from types import SimpleNamespace

from httpx2 import ConnectError, HTTPStatusError, Request, Response
from pydantic import ValidationError
import pytest

from app import worker
from app.core.config import HandlePrefixNotConfigured
from app.helpers.task_manager import (
    CheckpointAborted,
    Operation,
    SchedulerTaskError,
)
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


def _job() -> dict:
    return {
        "token": "token-1",
        "worker_id": "worker-1",
        "prefix": "21.11155",
        "issuer_profile": {},
        "payload": {},
    }


def _install_job_fakes(monkeypatch, error=None):
    events = []
    finalize_calls = []
    requeue_calls = []

    class Client:
        def __enter__(self):
            events.append("client_enter")
            return self

        def __exit__(self, *exc_info):
            return False

    class Scheduler:
        def __init__(self, client, result_log, **kwargs):
            events.append("scheduler_init")
            self.kwargs = kwargs

        def add_record(self, record):
            events.append("add_record")

        def record_reverse_dependencies(self):
            events.append("record_reverse_dependencies")

        def skip_previously_logged_tasks(self):
            events.append("skip_previously_logged_tasks")

        def prepare_dependency_graph(self):
            events.append("prepare_dependency_graph")
            return "graph"

        def pending_create_handlers(self):
            return []

        def apply_planned_pids(self, plan):
            events.append("apply_planned_pids")

        def execute_graph(self, graph):
            events.append("execute_graph")
            if error is not None:
                raise error

    def get_journal(token):
        events.append("get_journal")
        return []

    def ensure_plan(token, entries, worker_id):
        events.append("ensure_plan")
        return {}

    def finalize(*args, **kwargs):
        finalize_calls.append((args, kwargs))

    def requeue(*args, **kwargs):
        requeue_calls.append((args, kwargs))
        return "queued"

    def run_on_loop(loop, value):
        if inspect.iscoroutine(value):
            value.close()
            return None
        return value

    monkeypatch.setattr(
        worker, "create_service_client", lambda **kwargs: Client()
    )
    monkeypatch.setattr(worker, "decode_payload", lambda payload: ["record"])
    monkeypatch.setattr(worker, "Scheduler", Scheduler)
    monkeypatch.setattr(worker, "_get_journal", get_journal)
    monkeypatch.setattr(worker, "_ensure_plan", ensure_plan)
    monkeypatch.setattr(worker, "_finalize", finalize)
    monkeypatch.setattr(worker, "_requeue", requeue)
    monkeypatch.setattr(worker, "_run_on_loop", run_on_loop)
    return SimpleNamespace(
        events=events,
        finalize_calls=finalize_calls,
        requeue_calls=requeue_calls,
    )


def test_run_job_persists_plan_before_executing_and_finalizes(monkeypatch):
    fakes = _install_job_fakes(monkeypatch)

    worker._run_job(_job(), object())

    assert fakes.events == [
        "client_enter",
        "get_journal",
        "scheduler_init",
        "add_record",
        "record_reverse_dependencies",
        "skip_previously_logged_tasks",
        "prepare_dependency_graph",
        "ensure_plan",
        "apply_planned_pids",
        "execute_graph",
    ]
    assert fakes.finalize_calls == [(("token-1", "worker-1", "succeeded"), {})]
    assert fakes.requeue_calls == []


def test_run_job_requeues_retryable_failure(monkeypatch):
    fakes = _install_job_fakes(monkeypatch, error=ConnectError("down"))

    worker._run_job(_job(), object())

    assert fakes.finalize_calls == []
    assert fakes.requeue_calls == [
        (
            (
                "token-1",
                "worker-1",
                "dependency_unavailable",
                "Handle service is unavailable",
            ),
            {},
        )
    ]


def test_run_job_fails_terminal_error(monkeypatch):
    fakes = _install_job_fakes(
        monkeypatch, error=HandlePrefixNotConfigured("21.11155")
    )

    worker._run_job(_job(), object())

    assert fakes.requeue_calls == []
    ((args, kwargs),) = fakes.finalize_calls
    assert args == ("token-1", "worker-1", "failed")
    assert kwargs == {
        "failure_code": "service_credentials_unavailable",
        "failure_message": ("Server-side Handle credentials are unavailable"),
    }


def test_run_job_stops_without_writing_after_losing_lease(monkeypatch):
    fakes = _install_job_fakes(monkeypatch, error=CheckpointAborted())

    worker._run_job(_job(), object())

    assert fakes.finalize_calls == []
    assert fakes.requeue_calls == []


def test_run_worker_backs_off_after_claim_failure(monkeypatch):
    calls = []
    sleeps = []

    async def claim(worker_id):
        calls.append(worker_id)
        if len(calls) == 1:
            raise RuntimeError("database unavailable")
        raise asyncio.CancelledError

    async def sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(worker, "_claim", claim)
    monkeypatch.setattr(worker.asyncio, "sleep", sleep)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker.run_worker())

    assert sleeps == [worker.settings.SUBMISSION_WORKER_POLL_SECONDS]
