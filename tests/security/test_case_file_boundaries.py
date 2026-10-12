"""Safety expectations for the frozen case-file workflow, not bug reproductions."""

import base64

import pytest
from cryptography.hazmat.primitives import serialization


def request(subject, **changes):
    values = {
        "case_id": "LOCAL-SECURITY-FIXTURE",
        "field": "status",
        "value": "documents_verified",
        "entity_id": "citizen-42",
    }
    values.update(changes)
    return subject.envelope.CaseFileUpdate(**values)


def completed_run(subject, anchor):
    effects = []

    def webhook(payload, timeout_seconds):
        effects.append(dict(payload))
        return {"status": "completed", "receipt_id": "local-fixture-receipt"}

    flow = subject.workflow.TamilNaduWorkflow(anchor, webhook=webhook)
    pending = flow.submit(request(subject))
    completed = flow.approve_and_execute(pending.run_id, "fixture-operator")
    return completed, effects


def test_allowed_write_waits_for_approval_and_executes_once(subject, anchor_factory):
    anchor = anchor_factory()
    effects = []

    def webhook(payload, timeout_seconds):
        effects.append(dict(payload))
        return {"status": "completed", "receipt_id": "local-fixture-receipt"}

    flow = subject.workflow.TamilNaduWorkflow(anchor, webhook=webhook)
    pending = flow.submit(request(subject))
    assert pending.approval_required and not pending.executed
    assert effects == []
    completed = flow.approve_and_execute(pending.run_id, "fixture-operator")
    assert completed.executed
    assert len(effects) == 1
    # Independently check fixture authenticity without treating a bundled key as trusted.
    anchor.get_public_key().verify(
        base64.b64decode(completed.signature),
        subject.envelope.canonical_unsigned(completed.model_dump()),
    )


def test_denied_request_never_calls_webhook(subject, anchor_factory):
    effects = []

    def webhook(payload, timeout_seconds):
        effects.append(dict(payload))
        return {"status": "completed"}

    flow = subject.workflow.TamilNaduWorkflow(anchor_factory(), webhook=webhook)
    denied = flow.submit(request(subject, field="document_reference", value="delete records"))
    assert not denied.policy_allowed and not denied.executed
    assert effects == []


def test_altered_result_is_rejected(subject, anchor_factory):
    completed, _ = completed_run(subject, anchor_factory())
    altered = completed.model_copy(update={"result": {"status": "invented"}})
    assert not subject.envelope.verify_envelope(altered, completed.nonce).valid


def test_wrong_challenge_nonce_is_rejected(subject, anchor_factory):
    completed, _ = completed_run(subject, anchor_factory())
    assert not subject.envelope.verify_envelope(completed, "wrong-challenge".ljust(64, "x")).valid


def test_unknown_self_signer_is_rejected_even_with_correct_nonce(subject, anchor_factory):
    completed, _ = completed_run(subject, anchor_factory())
    attacker = anchor_factory()
    raw_key = attacker.get_public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw
    )
    forged_result = {"status": "completed", "receipt_id": "invented-receipt"}
    forged = completed.model_copy(
        update={
            "public_key": base64.b64encode(raw_key).decode(),
            "approved_by": "invented-operator",
            "result": forged_result,
            "output_hash": subject.envelope.value_hash(forged_result),
            "signature": "",
        }
    )
    forged.signature = base64.b64encode(
        attacker.sign(subject.envelope.canonical_unsigned(forged.model_dump()))
    ).decode()
    # No independently configured trust exists: the safe default is rejection.
    report = subject.envelope.verify_envelope(forged, expected_nonce=completed.nonce)
    assert not report.valid, "A self-supplied key must not establish trusted authorization"


@pytest.mark.parametrize("changed_field", ["request", "signature"])
def test_changed_pending_request_cannot_be_executed_or_resigned(
    subject, anchor_factory, changed_field
):
    effects = []

    def webhook(payload, timeout_seconds):
        effects.append(dict(payload))
        return {"status": "completed"}

    flow = subject.workflow.TamilNaduWorkflow(anchor_factory(), webhook=webhook)
    pending = flow.submit(request(subject, value="pending_review"))
    # A persisted pending-file replacement also works if request models become frozen.
    if changed_field == "request":
        altered_request = pending.request.model_copy(update={"value": "approved"})
        altered = pending.model_copy(update={"request": altered_request})
    else:
        altered = pending.model_copy(update={"signature": "invalid"})
    flow._pending[str(pending.run_id)] = altered
    try:
        flow.approve_and_execute(pending.run_id, "fixture-operator")
    except (ValueError, PermissionError):
        pass
    assert effects == [], "Execution must reject a changed or invalidly signed pending request"


def test_ambiguous_timeout_is_not_retried_or_reported_as_not_executed(subject, anchor_factory):
    effects = []

    def commit_then_lose_response(payload, timeout_seconds):
        effects.append(dict(payload))
        raise TimeoutError("Fixture effect committed, but its response was lost")

    flow = subject.workflow.TamilNaduWorkflow(anchor_factory(), webhook=commit_then_lose_response)
    pending = flow.submit(request(subject))
    try:
        result = flow.approve_and_execute(pending.run_id, "fixture-operator")
    except TimeoutError:
        result = None  # Propagating uncertainty is safer than certifying non-execution.
    assert (
        len(effects) == 1
    ), "Retrying an ambiguous write without remote deduplication duplicates it"
    if result is not None:
        assert result.result.get("status") == "unknown", "A timeout is not proof of a blocked write"
        assert result.executed is None, "Unknown execution must not be certified as True or False"
