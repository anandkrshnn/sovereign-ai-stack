import pytest
import time
import subprocess
import httpx
import hashlib
from sovereign_ai.common.hardware_trust import get_secure_anchor
from sovereign_ai.common.rats import EvidenceBundle

@pytest.fixture(scope="module")
def verifier_service():
    """Starts the Verifier Service in a background process for integration testing."""
    proc = subprocess.Popen(
        ["python", "sovereign_ai/services/verifier.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for service to start
    ready = False
    for _ in range(10):
        try:
            resp = httpx.get("http://127.0.0.1:8080/health", timeout=1.0)
            if resp.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(1)
    
    if not ready:
        proc.terminate()
        pytest.fail("Verifier service failed to start for integration tests.")
    
    yield "http://127.0.0.1:8080"
    
    proc.terminate()
    proc.wait()

def test_verifier_service_roundtrip(verifier_service):
    """
    Validates the end-to-end REST API flow for attestation verification.
    """
    base_url = verifier_service
    anchor = get_secure_anchor("service_test", backend="mock")
    nonce = hashlib.sha256(b"integration_test_nonce").hexdigest()
    quote = anchor.generate_quote(nonce, [0, 11])
    
    bundle = EvidenceBundle(
        nonce=nonce,
        merkle_root="0x123",
        quote=quote,
        bundle_signature="sig_abc"
    )

    payload = {
        "bundle": bundle.model_dump(mode='json'),
        "expected_nonce": nonce,
        "reference_version": "v0.1.0a2"
    }
    
    headers = {"X-API-Key": "sovereign_trust_preview_2026"}
    resp = httpx.post(f"{base_url}/verify", json=payload, headers=headers)
    
    assert resp.status_code == 200
    data = resp.json()
    assert data["is_valid"] is True
    assert data["checks"]["nonce_fresh"] is True

def test_verifier_service_invalid_api_key(verifier_service):
    """Ensures the verifier service rejects unauthorized requests."""
    base_url = verifier_service
    headers = {"X-API-Key": "wrong_key"}
    resp = httpx.get(f"{base_url}/reference-values", headers=headers)
    assert resp.status_code == 403
