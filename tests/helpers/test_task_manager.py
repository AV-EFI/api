from types import SimpleNamespace
from unittest.mock import MagicMock

from httpx2 import HTTPStatusError, Request, Response
import pytest

from app.helpers.task_manager import (
    CheckpointAborted,
    Operation,
    Scheduler,
    SchedulerTaskError,
    Task,
)


class _WorkVariant:
    pass


class _Handler:
    def __init__(self, name=("avefi:LocalResource", "local-1")):
        self.name = name
        self.tasks = {Operation.CREATE: object()}
        self.local_id = name[1]
        self.pid = None
        self.record = _WorkVariant()


class _Task:
    def __init__(self, handler, error=None):
        self.handler = handler
        self.operation = Operation.CREATE
        self.error = error
        self.executed = False

    def execute(self):
        self.executed = True
        if self.error is not None:
            raise self.error


def _scheduler(checkpoint, classifier=None):
    return Scheduler(
        client=MagicMock(),
        result_log=[],
        checkpoint=checkpoint,
        error_classifier=classifier,
    )


def test_execute_graph_checkpoints_structured_failure():
    handler = _Handler()
    task = _Task(handler, error=RuntimeError("boom"))
    entries = []
    scheduler = _scheduler(
        entries.append, classifier=lambda exc: ("remote_error", "safe")
    )

    with pytest.raises(SchedulerTaskError) as exc_info:
        scheduler.execute_graph({task: set()})

    assert exc_info.value.operation == "CREATE"
    assert exc_info.value.local_id == "local-1"
    assert entries == [
        {
            "outcome": "failed",
            "action": "CREATE",
            "pid": None,
            "local_id": "local-1",
            "record_type": "_WorkVariant",
            "error_code": "remote_error",
            "error_message": "safe",
        }
    ]


def test_execute_graph_propagates_lost_lease_without_checkpoint():
    entries = []
    scheduler = _scheduler(entries.append)
    task = _Task(_Handler(), error=CheckpointAborted())

    with pytest.raises(CheckpointAborted):
        scheduler.execute_graph({task: set()})

    assert entries == []


def test_apply_planned_pids_assigns_only_pending_creates():
    handler = _Handler()
    scheduler = _scheduler(lambda entry: None)
    scheduler.handlers = [handler]

    scheduler.apply_planned_pids({handler.name: "21.11155/PLANNED"})

    assert handler.pid == "21.11155/PLANNED"
    assert scheduler.pending_create_handlers() == [handler]


def test_apply_planned_pids_requires_a_plan_for_every_create():
    handler = _Handler()
    scheduler = _scheduler(lambda entry: None)
    scheduler.handlers = [handler]

    with pytest.raises(RuntimeError):
        scheduler.apply_planned_pids({})


def test_before_task_runs_before_execution():
    task = _Task(_Handler())
    calls = []

    def before(current):
        calls.append(current)

    scheduler = Scheduler(
        client=MagicMock(),
        result_log=[],
        before_task=before,
    )
    scheduler.execute_graph({task: set()})

    assert calls == [task]
    assert task.executed is True


def test_before_task_aborts_execution_when_lease_is_lost():
    task = _Task(_Handler())

    def before(current):
        raise CheckpointAborted

    scheduler = Scheduler(
        client=MagicMock(),
        result_log=[],
        before_task=before,
    )

    with pytest.raises(CheckpointAborted):
        scheduler.execute_graph({task: set()})

    assert task.executed is False


def _status_error(status: int) -> HTTPStatusError:
    request = Request("PUT", "https://handles.example/pid")
    response = Response(status, request=request)
    return HTTPStatusError("failed", request=request, response=response)


def _create_task(client):
    scheduler = SimpleNamespace(
        client=client,
        result_log=[],
        checkpoint=MagicMock(),
    )
    handler = SimpleNamespace(
        scheduler=scheduler,
        record=SimpleNamespace(category="avefi:WorkVariant"),
        pid="21.11155/PLANNED",
        local_id="local-1",
        name=("avefi:LocalResource", "local-1"),
    )
    return Task(Operation.CREATE, handler), handler, scheduler


def test_create_adopts_existing_record_after_412():
    client = MagicMock()
    client.create.side_effect = _status_error(412)
    client.get.return_value = "existing"
    replacement = SimpleNamespace()
    client.efi_from_response.return_value = (
        "21.11155/PLANNED",
        replacement,
    )
    task, handler, scheduler = _create_task(client)
    original = handler.record

    task.execute()

    client.create.assert_called_once_with(original, pid="21.11155/PLANNED")
    client.get.assert_called_once_with("21.11155/PLANNED")
    assert handler.pid == "21.11155/PLANNED"
    assert handler.record is replacement
    scheduler.checkpoint.assert_called_once()


def test_create_rejects_response_with_a_different_pid():
    client = MagicMock()
    client.efi_from_response.return_value = (
        "21.11155/OTHER",
        SimpleNamespace(),
    )
    task, _, _ = _create_task(client)

    with pytest.raises(RuntimeError):
        task.execute()


def test_create_propagates_non_412_status_error():
    client = MagicMock()
    client.create.side_effect = _status_error(503)
    task, _, _ = _create_task(client)

    with pytest.raises(HTTPStatusError):
        task.execute()

    client.get.assert_not_called()
