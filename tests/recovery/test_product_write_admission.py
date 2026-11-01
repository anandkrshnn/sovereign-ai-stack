"""Fail-closed product write admission; independent fixture remote counts effects."""

import json
from dataclasses import asdict
from urllib.request import Request, urlopen
from uuid import uuid4

import pytest
from order_remote import FIXTURE_TOKEN, FakeOrderAPI, payload_digest

from sovereign_ai.orchestration import (
    AllowListPolicy,
    ProductOrchestrator,
    Run,
    RunState,
    SQLiteExecutionJournal,
    Step,
    Task,
    ToolAdapter,
    ToolCall,
    ToolCallState,
    VolatileOrchestrator,
)

TOOL = "orders.create"
TENANT = "fixture-tenant"
ORDER = {"sku": "fixture-sku", "quantity": 1}


class FixtureOrderAdapter(ToolAdapter):
    name = TOOL

    def __init__(self, url):
        self.url = url
        self.calls = 0

    def _request(self, body, timeout_seconds):
        request = Request(
            self.url,
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {FIXTURE_TOKEN}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.load(response)

    def execute(self, arguments, timeout_seconds):
        self.calls += 1
        return self._request(arguments, timeout_seconds)

    def execute_attempt(self, arguments, timeout_seconds, context):
        self.calls += 1
        receipt = self._request(
            {"arguments": dict(arguments), "execution": asdict(context)}, timeout_seconds
        )
        context.validate_receipt(receipt)
        return receipt


class FixtureReadAdapter(ToolAdapter):
    name = "orders.read"

    def __init__(self):
        self.calls = 0

    def execute(self, _arguments, _timeout_seconds):
        self.calls += 1
        return {"orders": []}


def make_task_and_step(*, consequence: str):
    task = Task(tenant_id=TENANT, agent_id=uuid4(), idempotency_key=f"task-{uuid4()}")
    arguments = {
        "tenant_id": TENANT,
        "operation_key": str(uuid4()),
        "payload_digest": payload_digest(ORDER),
        "order": ORDER,
    }
    step = Step(
        name="create fixture order",
        consequence=consequence,
        tool_call=ToolCall(
            tool_name=TOOL,
            arguments=arguments,
            idempotency_key=arguments["operation_key"],
        ),
    )
    return task, step


def run_after_approval(runner, task, step):
    events = []
    runner.emit = events.append
    run = runner.run(task, [step], Run(task_id=task.id))
    if run.state is RunState.WAITING_APPROVAL:
        approval = next(event for event in events if event.event_type == "approval.requested")
        runner.approve(approval.data["approval_id"], "fixture-host")
        run = runner.run(task, [step], run)
    return run


def test_product_configuration_rejects_write_tool_without_journal_before_remote_dispatch(tmp_path):
    with FakeOrderAPI(tmp_path / "remote.sqlite", deduplicate=False) as remote:
        adapter = FixtureOrderAdapter(remote.url)
        policy = AllowListPolicy({TOOL}, tool_consequences={TOOL: "write"})
        with pytest.raises(ValueError, match="durable_journal_required_for_write"):
            ProductOrchestrator({TOOL: adapter}, policy, journal=None)
        assert adapter.calls == 0
        assert remote.counts() == {
            "arrivals": 0,
            "dispatches": 0,
            "unauthorized": 0,
            "orders": 0,
            "duplicate_effects": 0,
        }


def test_step_escalated_to_write_is_rejected_before_adapter_or_remote_dispatch(tmp_path):
    with FakeOrderAPI(tmp_path / "remote.sqlite", deduplicate=False) as remote:
        adapter = FixtureOrderAdapter(remote.url)
        policy = AllowListPolicy({TOOL}, tool_consequences={TOOL: "read"})
        runner = ProductOrchestrator({TOOL: adapter}, policy)
        task, step = make_task_and_step(consequence="write")

        run = run_after_approval(runner, task, step)

        assert run.state is RunState.FAILED
        assert run.error == "durable_journal_required_for_write"
        assert step.tool_call.state is ToolCallState.DENIED
        assert adapter.calls == 0
        assert remote.counts()["arrivals"] == remote.counts()["dispatches"] == 0
        assert remote.counts()["orders"] == 0


def test_product_read_step_runs_without_journal():
    adapter = FixtureReadAdapter()
    policy = AllowListPolicy({adapter.name}, tool_consequences={adapter.name: "read"})
    runner = ProductOrchestrator({adapter.name: adapter}, policy)
    task = Task(tenant_id=TENANT, agent_id=uuid4(), idempotency_key=f"task-{uuid4()}")
    step = Step(
        name="read fixture orders",
        consequence="read",
        tool_call=ToolCall(tool_name=adapter.name, idempotency_key=f"read-{uuid4()}", arguments={}),
    )

    result = runner.run(task, [step])

    assert result.state is RunState.SUCCEEDED
    assert adapter.calls == 1


def test_product_journal_write_dispatches_once_to_independent_fixture_remote(tmp_path):
    with (
        FakeOrderAPI(tmp_path / "remote.sqlite", deduplicate=False) as remote,
        SQLiteExecutionJournal(tmp_path / "execution.sqlite") as journal,
    ):
        adapter = FixtureOrderAdapter(remote.url)
        policy = AllowListPolicy({TOOL}, tool_consequences={TOOL: "write"})
        runner = ProductOrchestrator({TOOL: adapter}, policy, journal=journal)
        task, step = make_task_and_step(consequence="write")

        result = run_after_approval(runner, task, step)

        assert result.state is RunState.SUCCEEDED
        assert adapter.calls == 1
        assert remote.counts()["arrivals"] == remote.counts()["dispatches"] == 1
        assert remote.counts()["orders"] == 1
        assert journal.get((TENANT, TOOL, step.tool_call.idempotency_key)).state == "succeeded"


def test_product_configuration_requires_complete_host_consequence_registry():
    policy = AllowListPolicy({TOOL})
    with pytest.raises(ValueError, match="trusted_consequence_not_configured"):
        ProductOrchestrator({}, policy)


def test_product_configuration_rejects_unknown_host_consequence():
    policy = AllowListPolicy({TOOL}, tool_consequences={TOOL: "maybe-write"})
    with pytest.raises(ValueError, match="unknown_host_consequence"):
        ProductOrchestrator({}, policy)


def test_product_configuration_rejects_non_sqlite_journal():
    policy = AllowListPolicy({TOOL}, tool_consequences={TOOL: "write"})
    with pytest.raises(TypeError, match="requires_sqlite_execution_journal"):
        ProductOrchestrator({}, policy, journal=object())


def test_existing_attempt_bound_adapter_rejection_is_preserved(tmp_path):
    class LegacyAdapter(ToolAdapter):
        name = TOOL

        def __init__(self):
            self.calls = 0

        def execute(self, _arguments, _timeout_seconds):
            self.calls += 1
            return {"unexpected": "legacy adapter should not be invoked"}

    adapter = LegacyAdapter()
    policy = AllowListPolicy({TOOL}, tool_consequences={TOOL: "write"})
    with SQLiteExecutionJournal(tmp_path / "execution.sqlite") as journal:
        runner = ProductOrchestrator({TOOL: adapter}, policy, journal=journal)
        task, step = make_task_and_step(consequence="write")

        result = run_after_approval(runner, task, step)

        assert result.state is RunState.FAILED
        assert result.error == "attempt_bound_adapter_required"
        assert adapter.calls == 0
        assert journal.get((TENANT, TOOL, step.tool_call.idempotency_key)).state == "reserved"


def test_existing_missing_adapter_rejection_is_preserved(tmp_path):
    policy = AllowListPolicy({TOOL}, tool_consequences={TOOL: "write"})
    with SQLiteExecutionJournal(tmp_path / "execution.sqlite") as journal:
        runner = ProductOrchestrator({}, policy, journal=journal)
        task, step = make_task_and_step(consequence="write")

        result = run_after_approval(runner, task, step)

        assert result.state is RunState.FAILED
        assert result.error == "attempt_bound_adapter_required"
        assert journal.get((TENANT, TOOL, step.tool_call.idempotency_key)).state == "reserved"


def test_volatile_mode_is_named_warned_and_not_a_product_configuration(caplog):
    policy = AllowListPolicy({TOOL}, tool_consequences={TOOL: "write"})
    adapter = FixtureReadAdapter()

    with caplog.at_level("WARNING"):
        VolatileOrchestrator({adapter.name: adapter}, policy)

    assert "test/development only" in caplog.text
    with pytest.raises(TypeError, match="allow_volatile_for_testing"):
        ProductOrchestrator({TOOL: adapter}, policy, allow_volatile_for_testing=True)


@pytest.mark.parametrize("host_consequence", ["write", "destructive"])
@pytest.mark.parametrize("reported_consequence", ["read", None])
def test_policy_override_cannot_dispatch_host_write_without_journal(
    tmp_path, host_consequence, reported_consequence
):
    class UnderclassifyingPolicy(AllowListPolicy):
        def decide_step(self, task, step):
            return self.decide(task, step.tool_call).model_copy(
                update={"consequence": reported_consequence, "requires_approval": False}
            )

    with FakeOrderAPI(tmp_path / "remote.sqlite", deduplicate=False) as remote:
        adapter = FixtureOrderAdapter(remote.url)
        policy = UnderclassifyingPolicy({TOOL}, tool_consequences={TOOL: "read"})
        runner = ProductOrchestrator({TOOL: adapter}, policy)
        task, step = make_task_and_step(consequence=host_consequence)

        result = run_after_approval(runner, task, step)

        assert result.state is RunState.FAILED
        assert result.error == "durable_journal_required_for_write"
        assert step.tool_call.state is ToolCallState.DENIED
        assert adapter.calls == 0
        assert remote.counts() == {
            "arrivals": 0,
            "dispatches": 0,
            "unauthorized": 0,
            "orders": 0,
            "duplicate_effects": 0,
        }


@pytest.mark.parametrize("classification_source", ["host", "registry"])
@pytest.mark.parametrize("trusted_consequence", ["write", "destructive"])
@pytest.mark.parametrize("reported_consequence", ["read", None])
def test_policy_override_cannot_remove_mandatory_write_approval(
    tmp_path, classification_source, trusted_consequence, reported_consequence
):
    class UnderclassifyingPolicy(AllowListPolicy):
        def decide_step(self, task, step):
            return self.decide(task, step.tool_call).model_copy(
                update={"consequence": reported_consequence, "requires_approval": False}
            )

    with (
        FakeOrderAPI(tmp_path / "remote.sqlite", deduplicate=False) as remote,
        SQLiteExecutionJournal(tmp_path / "execution.sqlite") as journal,
    ):
        adapter = FixtureOrderAdapter(remote.url)
        registry = trusted_consequence if classification_source == "registry" else "read"
        host = trusted_consequence if classification_source == "host" else "read"
        policy = UnderclassifyingPolicy({TOOL}, tool_consequences={TOOL: registry})
        events = []
        runner = ProductOrchestrator({TOOL: adapter}, policy, journal=journal, emit=events.append)
        task, step = make_task_and_step(consequence=host)

        result = runner.run(task, [step])

        assert result.state is RunState.WAITING_APPROVAL
        decision = next(event for event in events if event.event_type == "policy.decided")
        assert decision.data["decision"]["consequence"] == trusted_consequence
        assert decision.data["decision"]["requires_approval"] is True
        assert adapter.calls == 0
        assert remote.counts()["arrivals"] == remote.counts()["dispatches"] == 0
        assert remote.counts()["orders"] == 0
        assert journal.get((TENANT, TOOL, step.tool_call.idempotency_key)) is None
        approval = next(event for event in events if event.event_type == "approval.requested")
        runner.approve(approval.data["approval_id"], "fixture-host")

        result = runner.run(task, [step], result)

        assert result.state is RunState.SUCCEEDED
        assert adapter.calls == 1
        assert remote.counts()["dispatches"] == remote.counts()["orders"] == 1


@pytest.mark.parametrize(
    ("override", "expected_state", "expected_consequence"),
    [
        ({"allowed": False, "reason": "extra_host_restriction"}, RunState.FAILED, None),
        ({"requires_approval": True}, RunState.WAITING_APPROVAL, "read"),
        ({"consequence": "destructive"}, RunState.WAITING_APPROVAL, "destructive"),
        ({"consequence": "unrecognized"}, RunState.FAILED, None),
    ],
)
def test_product_preserves_stricter_policy_decisions_and_rejects_unknown_classification(
    override, expected_state, expected_consequence
):
    class ExtendedPolicy(AllowListPolicy):
        def decide_step(self, task, step):
            return self.decide(task, step.tool_call).model_copy(update=override)

    adapter = FixtureReadAdapter()
    policy = ExtendedPolicy({adapter.name}, tool_consequences={adapter.name: "read"})
    events = []
    runner = ProductOrchestrator({adapter.name: adapter}, policy, emit=events.append)
    task = Task(tenant_id=TENANT, agent_id=uuid4(), idempotency_key=f"task-{uuid4()}")
    step = Step(
        name="read fixture orders",
        consequence="read",
        tool_call=ToolCall(tool_name=adapter.name, idempotency_key=f"read-{uuid4()}"),
    )

    result = runner.run(task, [step])

    assert result.state is expected_state
    assert adapter.calls == 0
    if expected_consequence is not None:
        decision = next(event for event in events if event.event_type == "policy.decided")
        assert decision.data["decision"]["consequence"] == expected_consequence
        assert decision.data["decision"]["requires_approval"] is True
    else:
        assert result.error == override.get("reason", "unknown_host_consequence")
