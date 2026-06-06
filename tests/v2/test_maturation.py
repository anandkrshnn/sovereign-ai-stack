import os

import pytest

from sovereign_ai.agent.tpm_signer import TPMSigner
from sovereign_ai.verify.nli_calibration import PlattCalibrator, get_calibrator
from sovereign_ai.verify.policy_z3 import HAS_Z3, PolicyVerifier


def test_tpm_signer_simulation():
    """Verify that the TPMSigner correctly falls back to simulation in non-HW environments."""
    signer = TPMSigner(tenant_id="test_tenant", backend="mock")
    payload = b"test_audit_event"
    signature = signer.sign_event(payload)

    assert signature is not None
    # SoftwareSimulatorAnchor (mock_sim.py) returns simulated hashes
    assert len(signature) > 0
    assert not signer.is_hardware_rooted


def test_nli_calibration_logic():
    """Verify that the Platt Calibrator correctly scales probabilities."""
    calibrator = PlattCalibrator(A=-1.0, B=0.0)

    # Probability 0.5 (logit 0) should remain 0.5 if A=-1, B=0
    # Formula: 1 / (1 + exp(-1 * 0 + 0)) = 1 / (1 + 1) = 0.5
    assert pytest.approx(calibrator.calibrate(0.5), 0.01) == 0.5

    # Probability 0.9 should be pushed higher if A is negative
    high_p = calibrator.calibrate(0.9)
    assert high_p > 0.5

    # Factory check
    factory_cal = get_calibrator("deberta-v3-base")
    assert factory_cal.A == -1.25


def test_policy_verifier_conflicts():
    """Verify that the Policy Verifier detects basic ABAC conflicts."""
    verifier = PolicyVerifier()
    policies = [
        {"principal": "alice", "resource": "file1", "action": "read", "effect": "allow"},
        {"principal": "alice", "resource": "file1", "action": "read", "effect": "deny"},
    ]

    conflicts = verifier.detect_conflicts(policies)
    # Our simplified implementation detects different actions on same p/r
    assert any("Conflict" in c for c in conflicts)


@pytest.mark.skipif(not HAS_Z3, reason="z3-solver not installed")
def test_z3_satisfiability():
    """Verify Z3 satisfiability check if available."""
    from z3 import And, Bool, Not

    verifier = PolicyVerifier()

    A = Bool("A")
    # Unsatisfiable: A and Not(A)
    assert not verifier.is_policy_satisfiable([A, Not(A)])
    # Satisfiable: A
    assert verifier.is_policy_satisfiable([A])
