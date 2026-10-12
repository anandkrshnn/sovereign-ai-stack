"""Authorization and idempotency expectations using a local adapter only."""

from uuid import uuid4

import pytest


def make_task(subject, tenant="tenant-a"):
    return subject.models.Task(
        tenant_id=tenant, agent_id=uuid4(), idempotency_key=f"fixture-task-{uuid4()}"
    )


def make_step(subject, value, tool="fixture", write=False):
    arguments = {"value": value}
    if write:
        arguments["consequence"] = "write"
    return subject.models.Step(
        name="fixture-step",
        consequence="write" if write else "read",
        tool_call=subject.models.ToolCall(
            tool_name=tool, arguments=arguments, idempotency_key="fixture-call-key"
        ),
    )


def make_runner(subject, allowed_tools=None):
    class LocalAdapter(subject.adapters.ToolAdapter):
        name = "fixture"

        def __init__(self):
            self.effects = []

        def execute(self, arguments, timeout_seconds):
            self.effects.append(dict(arguments))
            return {"value": arguments["value"]}

    adapter = LocalAdapter()
    outputs = []

    def verify(task, step, output):
        outputs.append((task.tenant_id, dict(output)))
        return subject.models.VerificationResult(passed=True, reason="local fixture verifier")

    runner = subject.runner.DeterministicOrchestrator(
        {"fixture": adapter, "other": adapter},
        subject.policy.AllowListPolicy(
            {"fixture", "other"} if allowed_tools is None else allowed_tools
        ),
        verify=verify,
    )
    return runner, adapter, outputs


def test_denied_tool_has_no_effect(subject):
    runner, adapter, _ = make_runner(subject, allowed_tools={"other"})
    run = runner.run(make_task(subject), [make_step(subject, "denied")])
    assert run.state == subject.models.RunState.FAILED
    assert adapter.effects == []


def test_write_waits_for_explicit_approval(subject):
    runner, adapter, _ = make_runner(subject)
    task = make_task(subject)
    step = make_step(subject, "approved-write", write=True)
    run = runner.run(task, [step])
    assert run.state == subject.models.RunState.WAITING_APPROVAL
    assert adapter.effects == []
    runner.approve(next(iter(runner._approvals)), "fixture-operator")
    resumed = runner.run(task, [step], run)
    assert resumed.state == subject.models.RunState.SUCCEEDED
    assert len(adapter.effects) == 1


def test_completed_run_is_not_executed_again(subject):
    runner, adapter, _ = make_runner(subject)
    task = make_task(subject)
    step = make_step(subject, "read-result")
    run = runner.run(task, [step])
    runner.run(task, [step], run)
    assert len(adapter.effects) == 1


def test_same_scoped_key_and_input_reuses_a_completed_result(subject):
    runner, adapter, outputs = make_runner(subject)
    first = runner.run(make_task(subject), [make_step(subject, "same-input")])
    second = runner.run(make_task(subject), [make_step(subject, "same-input")])
    assert first.state == second.state == subject.models.RunState.SUCCEEDED
    assert len(adapter.effects) == 1
    assert outputs[-1][1] == {"value": "same-input"}


def test_orchestrator_does_not_retry_an_ambiguous_write_without_remote_deduplication(subject):
    effects = []
    evidence = []

    class CommitThenTimeout(subject.adapters.ToolAdapter):
        name = "fixture"

        def execute(self, arguments, timeout_seconds):
            effects.append(dict(arguments))
            raise TimeoutError("Fixture effect committed, but its response was lost")

    runner = subject.runner.DeterministicOrchestrator(
        {"fixture": CommitThenTimeout()},
        subject.policy.AllowListPolicy({"fixture"}),
        record_evidence=evidence.append,
    )
    task = make_task(subject)
    step = make_step(subject, "regulated-write", write=True)
    step = step.model_copy(
        update={"tool_call": step.tool_call.model_copy(update={"max_attempts": 2})}
    )
    run = runner.run(task, [step])
    assert run.state == subject.models.RunState.WAITING_APPROVAL
    runner.approve(next(iter(runner._approvals)), "fixture-operator")
    resumed = runner.run(task, [step], run)
    assert len(effects) == 1, "A local cache is not remote deduplication after a lost response"
    assert resumed.state != subject.models.RunState.SUCCEEDED
    assert not evidence, "An unconfirmed write must not produce successful execution evidence"


@pytest.mark.parametrize("changed_field", ["arguments", "tool", "tenant"])
def test_approval_cannot_authorize_a_changed_execution(subject, changed_field):
    runner, adapter, _ = make_runner(subject)
    task = make_task(subject)
    step = make_step(subject, "original-write", write=True)
    run = runner.run(task, [step])
    assert run.state == subject.models.RunState.WAITING_APPROVAL
    runner.approve(next(iter(runner._approvals)), "fixture-operator")
    # Replace objects rather than mutating them: frozen schemas alone cannot fix this.
    if changed_field == "arguments":
        changed_call = step.tool_call.model_copy(
            update={"arguments": {"value": "different-write", "consequence": "write"}}
        )
        step = step.model_copy(update={"tool_call": changed_call})
    elif changed_field == "tool":
        changed_call = step.tool_call.model_copy(update={"tool_name": "other"})
        step = step.model_copy(update={"tool_call": changed_call})
    else:
        task = task.model_copy(update={"tenant_id": "tenant-b"})
    resumed = runner.run(task, [step], run)
    assert adapter.effects == [], f"Approval did not bind the execution's {changed_field}"
    assert resumed.state != subject.models.RunState.SUCCEEDED


@pytest.mark.parametrize("scope_change", ["tenant", "tool"])
def test_same_idempotency_key_in_another_scope_executes_independently(subject, scope_change):
    runner, adapter, outputs = make_runner(subject)
    first = runner.run(make_task(subject), [make_step(subject, "first-output")])
    second_task = make_task(subject, tenant="tenant-b" if scope_change == "tenant" else "tenant-a")
    second_step = make_step(
        subject, "second-output", tool="other" if scope_change == "tool" else "fixture"
    )
    second = runner.run(second_task, [second_step])
    assert first.state == second.state == subject.models.RunState.SUCCEEDED
    assert len(adapter.effects) == 2, "An unrelated scope must not reuse another call's result"
    assert outputs[-1][1] == {"value": "second-output"}


def test_same_scoped_key_with_different_input_is_rejected(subject):
    runner, adapter, outputs = make_runner(subject)
    runner.run(make_task(subject), [make_step(subject, "original-input")])
    second = runner.run(make_task(subject), [make_step(subject, "changed-input")])
    assert second.state == subject.models.RunState.FAILED, "Conflicting key reuse must fail closed"
    assert len(adapter.effects) == 1
    assert len(outputs) == 1, "Cached output must not be verified against a different input"


def test_server_classified_write_cannot_default_to_read_from_missing_arguments(subject):
    runner, adapter, _ = make_runner(subject)
    step = make_step(subject, "regulated-write")
    step = step.model_copy(update={"consequence": "write"})
    run = runner.run(make_task(subject), [step])
    assert adapter.effects == [], "Missing caller metadata must not downgrade a known write"
    assert run.state in {
        subject.models.RunState.WAITING_APPROVAL,
        subject.models.RunState.FAILED,
    }
