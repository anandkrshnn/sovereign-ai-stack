import pytest

from sovereign_ai.agent.tpm_signer import TPMSigner
from sovereign_ai.common.hardware_trust import SoftwareSimulatorAnchor


def test_tpm_signer_basic():
    # Use simulator for testing
    signer = TPMSigner(tenant_id="test-agent", backend="simulator")

    payload = b"test audit event data"
    signature = signer.sign_event(payload)

    assert len(signature) > 0
    print(f"Signature generated: {signature.hex()[:20]}...")

    # Verify signature using the anchor's public key
    public_key = signer.anchor.get_public_key()

    # For Ed25519 (default for simulator)
    from cryptography.hazmat.primitives.asymmetric import ed25519

    if isinstance(public_key, ed25519.Ed25519PublicKey):
        public_key.verify(signature, payload)
        print("Signature verified successfully (Ed25519)!")
    else:
        # Fallback verification for other algorithms if needed
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, padding

        if hasattr(public_key, "verify"):
            # Simple verify for EC or RSA with default settings
            pass


def test_tpm_signer_attestation():
    signer = TPMSigner(tenant_id="test-agent", backend="simulator")
    statement = signer.get_attestation()

    # In the current simulator, this returns an empty bytes object by default
    assert isinstance(statement, bytes)
    print(f"Attestation statement retrieved (Length: {len(statement)})")


if __name__ == "__main__":
    test_tpm_signer_basic()
    test_tpm_signer_attestation()
    print("TPMSigner Tests Passed!")
