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
def test_attestation_roundtrip_hardware_native():
    """
    Validates a cryptographic roundtrip using real RSA-PSS signing/verification.
    This simulates the TPM2_QUOTE path.
    """
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives import hashes, serialization
    import base64
    
    # 1. Setup: Create a real RSA key (simulating AIK)
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    
    # 2. Challenge
    challenge_nonce = hashlib.sha256(b"hardware_nonce").hexdigest()
    
    # 3. Attester Generates Quote
    quote_data_bytes = f"TPM2B_ATTEST_BEYOND_SIMULATOR_{challenge_nonce}".encode()
    signature = private_key.sign(
        quote_data_bytes,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH
        ),
        hashes.SHA256()
    )
    
    from sovereign_ai.common.schemas import AttestationQuote
    quote = AttestationQuote(
        type=EvidenceType.TPM2_QUOTE,
        quote_data=base64.b64encode(quote_data_bytes).decode(),
        pcr_values={0: "bios_hash", 11: "app_hash_v1"},
        firmware_version="TPM_PRO_v2",
        runtime_measurement="app_hash_v1",
        signature=base64.b64encode(signature).decode()
    )
    
    # 4. Verifier
    ref_values = {
        "app_hash": "app_hash_v1",
        "aik_public_key_pem": public_pem
    }
    verifier = AttestationVerifier(ref_values)
    
    bundle = EvidenceBundle(
        nonce=challenge_nonce,
        merkle_root="0x789",
        quote=quote,
        bundle_signature="outer_sig"
    )
    
    results = verifier.verify_bundle(bundle, challenge_nonce)
    assert results["is_valid"] is True
    assert results["checks"]["signature_valid"] is True
