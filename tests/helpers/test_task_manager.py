import graphlib
from types import SimpleNamespace
from unittest.mock import MagicMock

from avefi_schema import model_pydantic_v2 as efi
from httpx2 import HTTPStatusError, Request, Response
import pytest

from app.helpers.task_manager import (
    CheckpointAborted,
    Handler,
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


def _local(identifier):
    return {"category": "avefi:LocalResource", "id": identifier}


def _work(identifier, **links):
    document = {
        "category": "avefi:WorkVariant",
        "type": "Monographic",
        "has_primary_title": {"type": "PreferredTitle", "has_name": "X"},
        "has_identifier": [_local(identifier)],
    }
    document.update(links)
    return document


def _manifestation(identifier, work="w1", **links):
    document = {
        "category": "avefi:Manifestation",
        "has_primary_title": {"type": "TitleProper", "has_name": "X"},
        "has_identifier": [_local(identifier)],
        "is_manifestation_of": [_local(work)],
    }
    document.update(links)
    return document


def _item(identifier, manifestation="m1", **links):
    document = {
        "category": "avefi:Item",
        "has_primary_title": {"type": "TitleProper", "has_name": "X"},
        "has_identifier": [_local(identifier)],
        "is_item_of": _local(manifestation),
    }
    document.update(links)
    return document


def _graph(*documents):
    scheduler = Scheduler(client=MagicMock(), result_log=[])
    for document in documents:
        scheduler.add_record(
            efi.MovingImageRecordTypeAdapter.validate_python(document)
        )
    scheduler.record_reverse_dependencies()
    return scheduler.prepare_dependency_graph()


def test_mutual_same_as_is_not_an_ordering_edge():
    graph = _graph(
        _work("w1"),
        _manifestation("m1", same_as=[_local("m2")]),
        _manifestation("m2", same_as=[_local("m1")]),
        _item("i1", "m1"),
        _item("i2", "m2"),
    )

    assert list(graphlib.TopologicalSorter(graph).static_order())


def test_mutual_is_copy_of_is_not_an_ordering_edge():
    graph = _graph(
        _work("w1"),
        _manifestation("m1"),
        _item("i1", is_copy_of=[_local("i2")]),
        _item("i2", is_copy_of=[_local("i1")]),
    )

    assert list(graphlib.TopologicalSorter(graph).static_order())


def test_mutual_item_same_as_is_not_an_ordering_edge():
    graph = _graph(
        _work("w1"),
        _manifestation("m1"),
        _item("i1", same_as=[_local("i2")]),
        _item("i2", same_as=[_local("i1")]),
    )

    assert list(graphlib.TopologicalSorter(graph).static_order())


def test_a_hierarchy_cycle_is_still_rejected():
    graph = _graph(
        _work("w1", type="Analytic", is_part_of=[_local("w2")]),
        _work("w2", type="Analytic", is_part_of=[_local("w1")]),
    )

    with pytest.raises(graphlib.CycleError):
        list(graphlib.TopologicalSorter(graph).static_order())


def test_item_same_as_is_tracked_as_a_reference():
    scheduler = Scheduler(client=MagicMock(), result_log=[])
    record = efi.MovingImageRecordTypeAdapter.validate_python(
        _item("i1", same_as=[_local("i2")])
    )
    handler = Handler(scheduler, record=record)

    assert "same_as" in {attribute for attribute, _ in handler.iter_links()}
