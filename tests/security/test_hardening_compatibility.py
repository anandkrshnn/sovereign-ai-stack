"""Positive trust checks and bounded recovery behavior for the new contracts."""

import base64
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization


def approved(subject, anchor):
    flow = subject.workflow.TamilNaduWorkflow(anchor, tenant_id="tenant-a")
    req = subject.envelope.CaseFileUpdate(
        case_id="fixture", field="status", value="approved", entity_id="citizen-42"
    )
    pending = flow.submit(req)
    return flow, flow.approve_and_execute(pending.run_id, "fixture-operator")


def trusted_report(subject, flow, envelope, tenant="tenant-a"):
    return subject.envelope.verify_envelope(
        envelope,
        envelope.nonce,
        trusted_signers=flow.trusted_signers,
        expected_tenant_id=tenant,
    )


def resign(subject, anchor, envelope):
    return envelope.model_copy(
        update={
            "signature": base64.b64encode(
                anchor.sign(subject.envelope.canonical_unsigned(envelope.model_dump()))
            ).decode()
        }
    )


def test_registered_signer_verifies_and_roundtrips(subject, anchor_factory):
    flow, completed = approved(subject, anchor_factory())
    replay = subject.envelope.WorkflowEvidenceEnvelope.model_validate_json(
        completed.model_dump_json()
    )
    assert trusted_report(subject, flow, replay).decision == "allowed"
    assert trusted_report(subject, flow, replay).valid


def test_registered_signer_cannot_cross_expected_tenant(subject, anchor_factory):
    flow, completed = approved(subject, anchor_factory())
    assert not trusted_report(subject, flow, completed, tenant="tenant-b").valid


def test_unknown_signer_rejected_with_an_explicit_registry(subject, anchor_factory):
    flow, completed = approved(subject, anchor_factory())
    attacker = anchor_factory()
    raw_key = attacker.get_public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    forged = completed.model_copy(update={"public_key": base64.b64encode(raw_key).decode()})
    forged = resign(subject, attacker, forged)
    assert not trusted_report(subject, flow, forged).valid


def test_trusted_signature_cannot_hide_approval_digest_mismatch(subject, anchor_factory):
    anchor = anchor_factory()
    flow, completed = approved(subject, anchor)
    altered = resign(subject, anchor, completed.model_copy(update={"approval_digest": "0" * 64}))
    assert not trusted_report(subject, flow, altered).valid


def test_empty_principal_is_rejected_before_execution(subject, anchor_factory):
    flow = subject.workflow.TamilNaduWorkflow(anchor_factory())
    req = subject.envelope.CaseFileUpdate(
        case_id="fixture", field="status", value="approved", entity_id="citizen-42"
    )
    pending = flow.submit(req)
    with pytest.raises(ValueError, match="principal"):
        flow.approve_and_execute(pending.run_id, " ")


def test_signed_unknown_outcome_preserves_none_and_cannot_reopen_run(subject, anchor_factory):
    effects = []

    def lost_response(payload, timeout_seconds):
        effects.append(payload)
        raise TimeoutError("committed but response lost")

    flow = subject.workflow.TamilNaduWorkflow(
        anchor_factory(), webhook=lost_response, tenant_id="tenant-a"
    )
    req = subject.envelope.CaseFileUpdate(
        case_id="fixture", field="status", value="approved", entity_id="citizen-42"
    )
    pending = flow.submit(req)
    result = flow.approve_and_execute(pending.run_id, "fixture-operator")
    report = trusted_report(subject, flow, result)
    assert report.valid and report.decision == "unknown" and report.executed is None
    with pytest.raises(ValueError, match="already dispatched"):
        flow.load_pending(pending)
    assert len(effects) == 1


def test_response_without_confirmation_is_not_execution_proof(subject, anchor_factory):
    flow = subject.workflow.TamilNaduWorkflow(
        anchor_factory(),
        webhook=lambda payload, timeout_seconds: {"status": "completed"},
        tenant_id="tenant-a",
    )
    req = subject.envelope.CaseFileUpdate(
        case_id="fixture", field="status", value="approved", entity_id="citizen-42"
    )
    pending = flow.submit(req)
    result = flow.approve_and_execute(pending.run_id, "fixture-operator")
    assert result.executed is None
    assert trusted_report(subject, flow, result).decision == "unknown"


def runner_fixture(subject, execute, policy=None):
    class Adapter(subject.adapters.ToolAdapter):
        name = "fixture"

        def execute(self, arguments, timeout_seconds):
            return execute(arguments)

    runner = subject.runner.DeterministicOrchestrator(
        {"fixture": Adapter()}, policy or subject.policy.AllowListPolicy({"fixture"})
    )
    task = subject.models.Task(tenant_id="tenant-a", agent_id=uuid4(), idempotency_key="task")
    step = subject.models.Step(
        name="fixture",
        tool_call=subject.models.ToolCall(
            tool_name="fixture", arguments={"value": 1}, idempotency_key="call", max_attempts=3
        ),
    )
    return runner, task, step


def test_unknown_result_is_reserved_across_new_runs_in_one_process(subject):
    effects = []

    def lost_response(arguments):
        effects.append(arguments)
        raise TimeoutError("lost response")

    runner, task, step = runner_fixture(subject, lost_response)
    first = runner.run(task, [step])
    second = runner.run(task.model_copy(update={"id": uuid4()}), [step])
    assert first.state == second.state == subject.models.RunState.OUTCOME_UNKNOWN
    assert len(effects) == 1


def test_only_explicit_no_effect_failures_can_retry(subject):
    attempts = []
    effects = []

    def transient(arguments):
        attempts.append(arguments)
        if len(attempts) == 1:
            raise subject.adapters.RetryableAdapterError("no effect occurred")
        effects.append(arguments)
        return {"value": 1}

    runner, task, step = runner_fixture(subject, transient)
    assert runner.run(task, [step]).state == subject.models.RunState.SUCCEEDED
    assert len(attempts) == 2 and len(effects) == 1


def test_generic_adapter_error_is_not_a_safe_retry_signal(subject):
    effects = []

    def partial_write(arguments):
        effects.append(arguments)
        raise subject.adapters.AdapterError("partial write possible")

    runner, task, step = runner_fixture(subject, partial_write)
    assert runner.run(task, [step]).state == subject.models.RunState.OUTCOME_UNKNOWN
    assert len(effects) == 1


def test_registered_write_metadata_overrides_caller_read_claim(subject):
    effects = []
    policy = subject.policy.AllowListPolicy({"fixture"}, tool_consequences={"fixture": "write"})
    runner, task, step = runner_fixture(subject, lambda args: effects.append(args), policy)
    step.tool_call.arguments["consequence"] = "read"
    assert runner.run(task, [step]).state == subject.models.RunState.WAITING_APPROVAL
    assert effects == []


def test_standalone_policy_needs_trusted_metadata(subject):
    policy = subject.policy.AllowListPolicy({"fixture"})
    _, task, step = runner_fixture(subject, lambda args: {"value": 1})
    assert not policy.decide(task, step.tool_call).allowed


def test_expired_approval_cannot_dispatch(subject):
    effects = []
    runner, task, step = runner_fixture(subject, lambda args: effects.append(args))
    step.consequence = "write"
    run = runner.run(task, [step])
    approval_id = next(iter(runner._approvals))
    runner.approve(approval_id, "fixture-operator")
    runner._approvals[approval_id].expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    assert runner.run(task, [step], run).state == subject.models.RunState.FAILED
    assert effects == []


def test_trusted_classification_change_invalidates_existing_approval(subject):
    effects = []
    policy = subject.policy.AllowListPolicy({"fixture"}, tool_consequences={"fixture": "write"})
    runner, task, step = runner_fixture(subject, lambda args: effects.append(args), policy)
    run = runner.run(task, [step])
    runner.approve(next(iter(runner._approvals)), "fixture-operator")
    policy.tool_consequences["fixture"] = "destructive"
    assert runner.run(task, [step], run).state == subject.models.RunState.FAILED
    assert effects == []
