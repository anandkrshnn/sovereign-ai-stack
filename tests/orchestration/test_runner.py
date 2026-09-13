from sovereign_ai.orchestration import (
    AllowListPolicy,
    DeterministicOrchestrator,
    RunState,
    Step,
    Task,
    ToolCall,
    ToolCallState,
)
from sovereign_ai.orchestration.adapters import AdapterError, ToolAdapter
from sovereign_ai.orchestration.models import Agent, VerificationResult


class FakeAdapter(ToolAdapter):
    name = "fake"

    def __init__(self, failures=0):
        self.failures = failures
        self.calls = 0

    def execute(self, arguments, timeout_seconds):
        self.calls += 1
        if self.calls <= self.failures:
            raise AdapterError("transient")
        return {"value": arguments["value"]}


def make_task():
    agent = Agent(tenant_id="tenant", name="test")
    return Task(tenant_id="tenant", agent_id=agent.id, idempotency_key="task-1")


def test_retry_idempotency_and_evidence():
    adapter = FakeAdapter(failures=1)
    evidence = []
    runner = DeterministicOrchestrator(
        {"fake": adapter}, AllowListPolicy({"fake"}), record_evidence=evidence.append
    )
    task = make_task()
    step = Step(
        name="read",
        tool_call=ToolCall(
            tool_name="fake", arguments={"value": 3}, idempotency_key="call-1", max_attempts=2
        ),
    )
    run = runner.run(task, [step])
    assert run.state is RunState.SUCCEEDED
    assert adapter.calls == 2
    assert len(evidence) == 1
    runner.run(task, [step], run)
    assert adapter.calls == 2


def test_denied_tool_fails_closed():
    runner = DeterministicOrchestrator({}, AllowListPolicy({"other"}))
    task = make_task()
    step = Step(name="bad", tool_call=ToolCall(tool_name="fake", idempotency_key="call-2"))
    run = runner.run(task, [step])
    assert run.state is RunState.FAILED
    assert step.tool_call.state is ToolCallState.DENIED


def test_approval_pause_and_resume():
    adapter = FakeAdapter()
    runner = DeterministicOrchestrator({"fake": adapter}, AllowListPolicy({"fake"}))
    task = make_task()
    step = Step(
        name="write",
        tool_call=ToolCall(
            tool_name="fake",
            idempotency_key="call-3",
            arguments={"consequence": "write", "value": 1},
        ),
    )
    run = runner.run(task, [step])
    assert run.state is RunState.WAITING_APPROVAL
    approval_id = next(iter(runner._approvals))
    runner.approve(approval_id, "operator")
    run = runner.run(task, [step], run)
    assert run.state is RunState.SUCCEEDED
