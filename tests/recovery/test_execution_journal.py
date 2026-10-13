"""Focused journal/runner contracts; mock receipts are not provider validation."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, replace
from http.client import RemoteDisconnected
from multiprocessing import get_context
from urllib.error import HTTPError, URLError
from uuid import uuid4

import pytest

from sovereign_ai.orchestration import (
    AllowListPolicy,
    DeterministicOrchestrator,
    JournalConflict,
    JournalError,
    Run,
    RunState,
    SQLiteExecutionJournal,
    Step,
    Task,
    ToolCall,
    VerificationResult,
)
from sovereign_ai.orchestration.adapters import RetryableAdapterError, ToolAdapter

KEY = ("tenant", "orders.create", "operation")
DIGEST = "a" * 64


class BoundAdapter(ToolAdapter):
    name = "orders.create"

    def __init__(self, corrupt=None, error=None):
        self.calls = 0
        self.corrupt = corrupt
        self.error = error

    def execute(self, arguments, timeout_seconds):
        raise AssertionError("durable mode must not call the legacy adapter entry point")

    def execute_attempt(self, arguments, timeout_seconds, context):
        self.calls += 1
        if self.error:
            raise self.error
        output = {**asdict(context), "order_id": "mock-order"}
        if self.corrupt:
            output[self.corrupt] = (
                context.owner_generation + 1 if self.corrupt == "owner_generation" else "wrong"
            )
        return output


def fixture_runner(journal, adapter):
    events = []
    runner = DeterministicOrchestrator(
        {adapter.name: adapter},
        AllowListPolicy({adapter.name}, tool_consequences={adapter.name: "write"}),
        journal=journal,
        emit=events.append,
    )
    task = Task(tenant_id=KEY[0], agent_id=uuid4(), idempotency_key="task")
    step = Step(
        name="create order",
        tool_call=ToolCall(
            tool_name=KEY[1],
            idempotency_key=KEY[2],
            arguments={"sku": "fixture"},
            max_attempts=3,
        ),
    )
    return runner, events, task, step


def submit(runner, events, task, step):
    run = runner.run(task, [step], Run(task_id=task.id))
    assert run.state is RunState.WAITING_APPROVAL
    requested = [
        event
        for event in events
        if event.event_type == "approval.requested" and event.run_id == str(run.id)
    ]
    runner.approve(requested[-1].data["approval_id"], "fixture-host")
    return runner.run(task, [step], run)


def test_WAL_FULL_and_exclusive_live_owner(tmp_path):
    path = tmp_path / "journal.sqlite"
    with SQLiteExecutionJournal(path) as journal:
        assert journal.durability_settings() == ("wal", 2)
        with pytest.raises(JournalError, match="another_journal_owner"):
            SQLiteExecutionJournal(path)
        journal.prepare(KEY, DIGEST)
        assert journal.get(KEY).state == "reserved"
    with SQLiteExecutionJournal(path) as recovered:
        assert recovered.get(KEY).context.owner_generation == 2


@pytest.mark.parametrize("settings", [("delete", 2), ("wal", 1)])
def test_durability_readback_failure_rejects_startup(tmp_path, monkeypatch, settings):
    with monkeypatch.context() as patch:
        patch.setattr(SQLiteExecutionJournal, "durability_settings", lambda _self: settings)
        with pytest.raises(JournalError, match="WAL_FULL_readback"):
            SQLiteExecutionJournal(tmp_path / "journal.sqlite")
    # Failed initialization must not leak the process lock.
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        assert journal.durability_settings() == ("wal", 2)


def test_digest_conflict_and_tenant_tool_scoping(tmp_path):
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        first = journal.prepare(KEY, DIGEST)
        assert journal.prepare(KEY, DIGEST).context.attempt_id == first.context.attempt_id
        with pytest.raises(JournalConflict):
            journal.prepare(KEY, "b" * 64)
        other_tenant = journal.prepare(("other", KEY[1], KEY[2]), DIGEST)
        other_tool = journal.prepare((KEY[0], "another.tool", KEY[2]), DIGEST)
        assert (
            len(
                {
                    first.context.attempt_id,
                    other_tenant.context.attempt_id,
                    other_tool.context.attempt_id,
                }
            )
            == 3
        )
        assert journal.get(KEY).state == "reserved"


def test_barrier_rejects_stale_generation_and_second_dispatch(tmp_path):
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        record = journal.prepare(KEY, DIGEST)
        assert not journal.begin_dispatch(replace(record.context, owner_generation=99))
        assert journal.get(KEY).state == "reserved"
        assert journal.begin_dispatch(record.context)
        assert not journal.begin_dispatch(record.context)
        assert journal.get(KEY).state == "in_flight"


def reserve_in_child(path, pipe, after_barrier):
    # Parent imported the ordinary package; the POSIX fork only exercises journal
    # ownership/process death. The HTTP recovery slice uses fresh Python workers.
    with SQLiteExecutionJournal(path) as journal:
        record = journal.prepare(KEY, DIGEST)
        if after_barrier:
            assert journal.begin_dispatch(record.context)
        pipe.send(record.context)
        pipe.recv()  # Parent SIGKILLs this process, rather than closing the journal.


@pytest.mark.parametrize("after_barrier", [False, True], ids=["reserved", "in-flight"])
def test_SIGKILL_recovery_retains_attempt_and_distinguishes_dispatch_boundary(
    tmp_path, after_barrier
):
    context = get_context("fork")
    parent, child = context.Pipe()
    path = tmp_path / "journal.sqlite"
    process = context.Process(target=reserve_in_child, args=(path, child, after_barrier))
    process.start()
    child.close()
    try:
        assert parent.poll(10), "child failed to persist its reservation/barrier"
        original = parent.recv()
        with pytest.raises(JournalError, match="another_journal_owner"):
            SQLiteExecutionJournal(path)
        process.kill()
        process.join(5)
        assert process.exitcode == -9
        with SQLiteExecutionJournal(path) as journal:
            recovered = journal.get(KEY)
            assert recovered.context.attempt_id == original.attempt_id
            assert recovered.context.owner_generation == original.owner_generation + 1
            assert recovered.state == ("outcome_unknown" if after_barrier else "reserved")
            assert not journal.begin_dispatch(original)
            assert journal.begin_dispatch(recovered.context) is (not after_barrier)
    finally:
        parent.close()
        if process.is_alive():
            process.kill()
        process.join(5)


def test_closed_owner_and_unsupported_schema_fail_closed(tmp_path):
    import sqlite3

    path = tmp_path / "journal.sqlite"
    journal = SQLiteExecutionJournal(path)
    record = journal.prepare(KEY, DIGEST)
    journal.close()
    with pytest.raises(JournalError, match="journal_is_closed"):
        journal.begin_dispatch(record.context)
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA user_version=99")
    with pytest.raises(JournalError, match="unsupported_journal_schema"):
        SQLiteExecutionJournal(path)


def test_durable_success_cache_keeps_exact_attempt_and_does_not_dispatch(tmp_path):
    path = tmp_path / "journal.sqlite"
    adapter = BoundAdapter()
    with SQLiteExecutionJournal(path) as journal:
        runner, events, task, step = fixture_runner(journal, adapter)
        assert submit(runner, events, task, step).state is RunState.SUCCEEDED
        record = journal.get(KEY)
        assert record.evidence["attempt_id"] == record.context.attempt_id
        assert step.tool_call.arguments == {"sku": "fixture"}
    with SQLiteExecutionJournal(path) as recovered:
        runner, events, task, step = fixture_runner(recovered, adapter)
        assert submit(runner, events, task, step).state is RunState.SUCCEEDED
        assert recovered.get(KEY).context.attempt_id == record.context.attempt_id
        assert adapter.calls == 1


@pytest.mark.parametrize(
    "corrupt",
    [
        "tenant_id",
        "tool_name",
        "operation_key",
        "request_digest",
        "attempt_id",
        "owner_generation",
        "downstream_key",
    ],
)
def test_unbound_receipt_is_unknown_and_never_retried(tmp_path, corrupt):
    adapter = BoundAdapter(corrupt=corrupt)
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        runner, events, task, step = fixture_runner(journal, adapter)
        assert submit(runner, events, task, step).state is RunState.OUTCOME_UNKNOWN
        assert submit(runner, events, task, step).state is RunState.OUTCOME_UNKNOWN
        assert adapter.calls == 1
        assert journal.get(KEY).state == "outcome_unknown"
        assert journal.get(KEY).evidence is None


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("lost response"),
        RetryableAdapterError("legacy unbound no-effect hint"),
        HTTPError("http://fixture.invalid/orders", 500, "server error", None, None),
        RemoteDisconnected("response dropped"),
        ConnectionResetError("reset after send"),
        URLError("connection failed"),
    ],
    ids=[
        "timeout",
        "legacy-retry-hint",
        "http-500",
        "dropped-response",
        "connection-reset",
        "url-error",
    ],
)
def test_durable_adapter_errors_do_not_authorize_retries(tmp_path, error):
    adapter = BoundAdapter(error=error)
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        runner, events, task, step = fixture_runner(journal, adapter)
        run = submit(runner, events, task, step)
        assert run.state is RunState.OUTCOME_UNKNOWN
        assert run.attempts == adapter.calls == 1
        assert journal.get(KEY).state == "outcome_unknown"
        assert journal.get(KEY).evidence is None


def test_approval_binding_precedes_journal_reservation(tmp_path):
    adapter = BoundAdapter()
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        runner, events, task, step = fixture_runner(journal, adapter)
        run = runner.run(task, [step])
        step.tool_call.arguments["sku"] = "changed-after-approval-request"
        runner.approve(events[-1].data["approval_id"], "fixture-host")
        run = runner.run(task, [step], run)
        assert run.state is RunState.FAILED
        assert run.error == "approval_request_changed_or_expired"
        assert journal.get(KEY) is None
        assert adapter.calls == 0


def test_semantic_rejection_does_not_erase_confirmed_remote_effect(tmp_path):
    adapter = BoundAdapter()
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        runner, events, task, step = fixture_runner(journal, adapter)
        runner.verify = lambda *_args: VerificationResult(passed=False, reason="semantic rejection")
        assert submit(runner, events, task, step).state is RunState.FAILED
        assert journal.get(KEY).state == "succeeded"
        assert submit(runner, events, task, step).state is RunState.FAILED
        assert adapter.calls == 1


def test_completion_storage_failure_preserves_unknown(tmp_path, monkeypatch):
    adapter = BoundAdapter()
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        runner, events, task, step = fixture_runner(journal, adapter)

        def fail_complete(*_args):
            raise OSError("simulated storage failure")

        monkeypatch.setattr(journal, "complete", fail_complete)
        assert submit(runner, events, task, step).state is RunState.OUTCOME_UNKNOWN
        assert journal.get(KEY).state == "outcome_unknown"
        assert submit(runner, events, task, step).state is RunState.OUTCOME_UNKNOWN
        assert adapter.calls == 1


def test_concurrent_reservation_and_barrier_have_one_winner(tmp_path):
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        with ThreadPoolExecutor(max_workers=2) as pool:
            records = list(pool.map(lambda _index: journal.prepare(KEY, DIGEST), range(2)))
            assert records[0].context.attempt_id == records[1].context.attempt_id
            permitted = list(pool.map(journal.begin_dispatch, [item.context for item in records]))
        assert sorted(permitted) == [False, True]
        assert journal.get(KEY).state == "in_flight"


def test_unsupported_adapter_cannot_dispatch_or_hide_existing_unknown(tmp_path):
    class LegacyAdapter(ToolAdapter):
        name = "orders.create"
        calls = 0

        def execute(self, arguments, timeout_seconds):
            self.calls += 1
            raise AssertionError("unsupported adapter was dispatched")

    legacy = LegacyAdapter()
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        runner, events, task, step = fixture_runner(journal, legacy)
        assert submit(runner, events, task, step).state is RunState.FAILED
        assert journal.get(KEY).state == "reserved"
        bound = BoundAdapter(error=TimeoutError("lost response"))
        runner, events, task, step = fixture_runner(journal, bound)
        assert submit(runner, events, task, step).state is RunState.OUTCOME_UNKNOWN
        runner, events, task, step = fixture_runner(journal, legacy)
        assert submit(runner, events, task, step).state is RunState.OUTCOME_UNKNOWN
        assert legacy.calls == 0
        assert bound.calls == 1


def test_cached_confirmation_digest_mismatch_never_redispatches(tmp_path):
    import sqlite3
    from contextlib import closing

    path = tmp_path / "journal.sqlite"
    adapter = BoundAdapter()
    with SQLiteExecutionJournal(path) as journal:
        runner, events, task, step = fixture_runner(journal, adapter)
        assert submit(runner, events, task, step).state is RunState.SUCCEEDED
        with closing(sqlite3.connect(path)) as db, db:
            db.execute(
                "UPDATE attempts SET evidence_json=json_set(evidence_json,'$.record_hash','wrong')"
            )
        assert submit(runner, events, task, step).state is RunState.OUTCOME_UNKNOWN
        assert adapter.calls == 1


def test_boolean_generation_is_not_an_integer_receipt_binding(tmp_path):
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        context = journal.prepare(KEY, DIGEST).context
        with pytest.raises(ValueError, match="remote_receipt_not_bound"):
            context.validate_receipt({**asdict(context), "owner_generation": True})


def test_barrier_failure_cannot_call_adapter(tmp_path, monkeypatch):
    adapter = BoundAdapter()
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        runner, events, task, step = fixture_runner(journal, adapter)

        def fail_barrier(*_args):
            raise OSError("simulated dispatch-barrier storage failure")

        monkeypatch.setattr(journal, "begin_dispatch", fail_barrier)
        assert submit(runner, events, task, step).state is RunState.OUTCOME_UNKNOWN
        assert journal.get(KEY).state == "reserved"
        assert adapter.calls == 0


def test_forked_child_cannot_reuse_parent_journal_connection(tmp_path):
    context = get_context("fork")
    parent, child = context.Pipe()
    with SQLiteExecutionJournal(tmp_path / "journal.sqlite") as journal:
        record = journal.prepare(KEY, DIGEST)

        def inherited_owner():
            try:
                journal.begin_dispatch(record.context)
            except JournalError as exc:
                child.send(str(exc))
            else:
                child.send("unsafe inherited dispatch")

        process = context.Process(target=inherited_owner)
        process.start()
        child.close()
        try:
            assert parent.poll(5)
            assert parent.recv() == "journal_cannot_be_inherited_across_processes"
            process.join(5)
            assert process.exitcode == 0
            assert journal.get(KEY).state == "reserved"
            assert journal.begin_dispatch(record.context)
        finally:
            parent.close()
            if process.is_alive():
                process.kill()
            process.join(5)
