import pytest
import hashlib
from sovereign_ai.common.hardware_trust import get_secure_anchor
from sovereign_ai.common.rats import EvidenceBundle, AttestationVerifier
from sovereign_ai.common.schemas import EvidenceType

def test_attestation_roundtrip_simulator():
    """
    Validates the full Attestation Roundtrip using the software simulator.
    Ensures that the factory, evidence bundle, and verifier work in concert.
    """
    tenant_id = "test_integration_tenant"
    anchor = get_secure_anchor(tenant_id, backend="mock")
    
    # 1. Challenge from Verifier
    challenge_nonce = hashlib.sha256(b"integration_nonce").hexdigest()

    # 2. Attester Generates Quote
    pcrs = [0, 11]
    quote = anchor.generate_quote(challenge_nonce, pcrs)
    assert quote.type == EvidenceType.MOCK_SIM
    
    # 3. Packaging into EvidenceBundle
    merkle_root = "0x" + hashlib.sha256(b"root_v1").hexdigest()
    bundle = EvidenceBundle(
        nonce=challenge_nonce,
        merkle_root=merkle_root,
        quote=quote,
        bundle_signature="integration_sig"
    )
    
    # 4. Verification
    ref_values = {"app_hash": quote.runtime_measurement}
    verifier = AttestationVerifier(ref_values)
    
    results = verifier.verify_bundle(bundle, challenge_nonce)
    
    assert results["is_valid"] is True
    assert results["checks"]["nonce_fresh"] is True
    assert results["checks"]["measurements_valid"] is True
    assert results["checks"]["structure_valid"] is True

def test_evidence_bundle_pydantic_validation():
    """Ensures that EvidenceBundle enforces nonce length and other constraints."""
    with pytest.raises(ValueError):
        EvidenceBundle(
            nonce="short", # Should fail min_length=32
            merkle_root="0x1",
            bundle_signature="sig"
        )
