import json
from pathlib import Path

import pytest

from sovereign_ai.common.hardware_trust import SoftwareSimulatorAnchor
from sovereign_ai.workflows.tamilnadu_seva import (
    CaseFileUpdate,
    TamilNaduWorkflow,
    WorkflowEvidenceEnvelope,
    verify_envelope,
)


def request(**overrides):
    values = {
        "case_id": "TN-ES-1001",
        "field": "status",
        "value": "documents_verified",
        "entity_id": "citizen-42",
    }
    values.update(overrides)
    return CaseFileUpdate(**values)


def test_approved_webhook_run_is_replayable_and_tamper_evident():
    flow = TamilNaduWorkflow(SoftwareSimulatorAnchor("tn-test"))
    pending = flow.submit(request())
    assert pending.policy_allowed and pending.approval_required and not pending.executed
    approved = flow.approve_and_execute(pending.run_id, "operator-1")
    report = verify_envelope(approved, approved.nonce)
    assert report.valid is True and report.decision == "allowed"
    replay = WorkflowEvidenceEnvelope.model_validate_json(approved.model_dump_json())
    replay_report = verify_envelope(replay)
    assert replay_report.valid is True and replay_report.decision == "allowed"
    tampered = approved.model_copy(update={"result": {"updated": "different"}})
    tampered_report = verify_envelope(tampered)
    assert not tampered_report.valid
    assert tampered_report.decision == "invalid"


def test_destructive_action_is_denied_without_execution():
    flow = TamilNaduWorkflow(SoftwareSimulatorAnchor("tn-deny"))
    pending = flow.submit(request(field="document_reference", value="delete all documents"))
    assert not pending.policy_allowed
    assert not pending.executed
    assert not flow._pending
    report = verify_envelope(pending)
    assert report.valid is True
    assert report.decision == "denied"
    assert report.executed is False
    assert report.policy_allowed is False


def test_webhook_timeout_is_retried_and_blocked():
    attempts = []

    def timeout(_payload, timeout_seconds):
        attempts.append(timeout_seconds)
        raise TimeoutError("offline")

    flow = TamilNaduWorkflow(SoftwareSimulatorAnchor("tn-timeout"), webhook=timeout)
    pending = flow.submit(request())
    result = flow.approve_and_execute(pending.run_id, "operator-1")
    assert attempts == [30, 30]
    assert result.result["status"] == "blocked"
    assert not result.executed
    report = verify_envelope(result)
    assert report.valid is True
    assert report.decision == "blocked"
    assert report.executed is False


@pytest.mark.parametrize(
    "case,expected_allowed",
    [
        ({"field": "status", "value": "documents_verified"}, True),
        ({"field": "address", "value": "Chennai"}, True),
        ({"field": "document_reference", "value": "DOC-1"}, True),
        ({"field": "status", "value": "pending_review"}, True),
        ({"field": "address", "value": "Madurai"}, True),
        ({"field": "status", "value": "approved"}, True),
        ({"field": "address", "value": "Salem"}, True),
        ({"field": "document_reference", "value": "CERT-10"}, True),
        ({"field": "status", "value": "rejected"}, True),
        ({"field": "address", "value": "Coimbatore"}, True),
        ({"field": "document_reference", "value": "DOC-20"}, True),
        ({"field": "status", "value": "in_review"}, True),
        ({"field": "address", "value": "Tiruchirappalli"}, True),
        ({"field": "status", "value": "escalated"}, True),
        ({"field": "document_reference", "value": "SCAN-3"}, True),
        ({"field": "document_reference", "value": "delete records"}, False),
        ({"field": "document_reference", "value": "delete case"}, False),
        ({"field": "document_reference", "value": "delete documents"}, False),
        ({"field": "status", "value": "documents_verified", "entity_id": "citizen-43"}, False),
        ({"field": "status", "value": "documents_verified", "amount_inr": 9000000}, False),
    ],
)
def test_twenty_case_workflow_fixture(case, expected_allowed):
    flow = TamilNaduWorkflow(SoftwareSimulatorAnchor("tn-fixture"))
    evidence = flow.submit(request(**case))
    if not expected_allowed:
        assert not evidence.policy_allowed
        assert not evidence.executed
        report = verify_envelope(evidence)
        assert report.valid is True
        assert report.decision == "denied"
        assert report.executed is False
    else:
        completed = flow.approve_and_execute(evidence.run_id, "fixture-operator")
        report = verify_envelope(completed)
        assert report.valid is True
        assert report.decision == "allowed"
        assert report.executed is True
