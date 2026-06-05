import pytest
import time
import subprocess
import httpx
import base64
import os
from sovereign_ai.pipeline import SovereignPipeline, Config
from sovereign_ai.common.hardware_trust import get_secure_anchor
from sovereign_ai.rag.schemas import Document

@pytest.fixture(scope="module")
def verifier_service(tmp_path_factory):
    """Starts the Verifier Service in a background process for integration testing."""
    # Ensure port 8080 is used as configured in verifier.py
    env = os.environ.copy()
    env["VERIFIER_API_KEY"] = "sovereign_trust_preview_2026"
    log_path = tmp_path_factory.getbasetemp() / "verifier_service.log"
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        ["python", "sovereign_ai/services/verifier.py"],
        stdout=log_file,
        stderr=log_file,
        env=env
    )
    
    # Wait for service to start
    ready = False
    for _ in range(10):
        try:
            # Let's hit the health check
            resp = httpx.get("http://127.0.0.1:8080/health", timeout=1.0)
            if resp.status_code == 200:
                ready = True
                break
        except Exception:
            time.sleep(1)
            
    if not ready:
        proc.terminate()
        log_file.close()
        with open(log_path, "r") as f:
            logs = f.read()
        pytest.fail(f"Verifier service failed to start. Logs: {logs}")
        
    yield "http://127.0.0.1:8080"
    
    proc.terminate()
    proc.wait()
    log_file.close()

@pytest.mark.asyncio
async def test_isolated_nli_and_policy_verification(verifier_service, tmp_path):
    """
    Validates that SovereignPipeline routes NLI and SMT checks to the isolated verifier service
    and behaves correctly when it receives responses.
    """
    db_path = tmp_path / "rag.db"
    policy_path = tmp_path / "policy.yaml"
    
    with open(policy_path, "w") as f:
        f.write("""
version: "1.1.0a2"
allow:
  - tenant_id: "isolated_tenant"
    roles: ["user"]
    classifications: ["public"]
""")

    # 1. Config with remote/isolated verifier settings
    config = Config(
        db_path=str(db_path),
        policy_path=str(policy_path),
        tenant_id="isolated_tenant",
        principal="alice",
        enable_verification=True,
        isolated_verifier_url=verifier_service,
        isolated_verifier_key="sovereign_trust_preview_2026"
    )
    
    pipeline = SovereignPipeline(config)
    
    # Mock generator to avoid loading/downloading 1.5B parameters model
    from unittest.mock import MagicMock
    from sovereign_ai.rag.generator import QwenGenerator
    mock_gen = MagicMock(spec=QwenGenerator)
    mock_gen.model_name = "mock-qwen-1.5b"
    mock_gen.generate.return_value = "The secure vault holds the gold credentials."
    pipeline._engine.generator = mock_gen
    
    # Ingest document with classification matching policy
    doc = Document(
        doc_id="doc1",
        source="doc_source",
        content="The secure vault holds the gold credentials.",
        tenant_id="isolated_tenant",
        classification="public"
    )
    await pipeline.ingest([doc])
    
    # Query: Should query the isolated verifier service for post-gen NLI check
    res = await pipeline.ask("where are the gold credentials?")
    
    # Assert NLI evaluation was performed remotely (verification key should be in metadata)
    print("DEBUG RES ANSWER:", res.answer)
    print("DEBUG RES SOURCES:", res.sources)
    print("DEBUG VERIFICATION METADATA:", res.metadata.get("verification"))
    assert "verification" in res.metadata
    assert res.metadata["verification"]["passed"] is True
    assert "gold credentials" in res.answer.lower()
    
    # 2. Directly verify the remote SMT policy verification endpoint
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{verifier_service}/verify/policy",
            json={
                "principal": "alice",
                "resource": "vault",
                "action": "query",
                "policies": [
                    {
                        "principal": "alice",
                        "resource": "vault",
                        "action": "query",
                        "effect": "allow"
                    }
                ],
                "check_type": "authorize"
            },
            headers={"X-API-Key": "sovereign_trust_preview_2026"}
        )
        assert resp.status_code == 200
        policy_res = resp.json()
        assert policy_res["is_authorized"] is True
        
    await pipeline.close()

def test_tpm_key_sealing():
    """
    Tests the seal_key and unseal_key methods under simulated Windows/Linux trust anchors.
    """
    anchor = get_secure_anchor("test_tenant", backend="mock")
    secret = b"my_super_secret_sqlcipher_password_123"
    
    # Seal the secret
    sealed = anchor.seal_key(secret)
    assert sealed != secret
    
    # Unseal the secret
    unsealed = anchor.unseal_key(sealed)
    assert unsealed == secret
