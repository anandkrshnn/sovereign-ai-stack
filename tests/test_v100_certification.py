import pytest
import yaml
import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch
from local_rag.policy import PolicyEngine, Principal, AccessRequest
from local_rag.schemas import SearchResult, AuditRecord
from local_rag.audit import AuditLogger, KeyringProvider

@pytest.fixture
def abac_policy(tmp_path):
    policy_path = tmp_path / "v100_policy.yaml"
    policy_data = {
        "version": "1.0.0-GA",
        "allow": [
            {
                "roles": ["admin"],
                "intents": ["research", "audit"],
                "classifications": ["all"]
            },
            {
                "roles": ["analyst"],
                "intents": ["general"],
                "classifications": ["public", "internal"]
            }
        ],
        "deny": [
            {
                "intents": ["treatment"],
                "classifications": ["secret"]
            }
        ],
        "limits": {"max_results": 10}
    }
    with open(policy_path, "w") as f:
        yaml.dump(policy_data, f)
    return str(policy_path)

def test_abac_matrix_integration(abac_policy):
    """
    Sovereign Certification: Verify Principal/Intent/Classification matrix.
    """
    engine = PolicyEngine(abac_policy)
    
    results = [
        SearchResult(doc_id="d1", chunk_id="c1", text="Public", score=0.9, metadata={"classification": "public"}),
        SearchResult(doc_id="d2", chunk_id="c2", text="Secret", score=0.9, metadata={"classification": "secret"}),
    ]
    
    # 1. Scenario: Analyst / General intent -> Should see public but NOT secret
    analyst_request = AccessRequest(
        principal=Principal(id="u1", tenant_id="t1", roles=["analyst"], classifications=["public"]),
        intent="general",
        query="help"
    )
    decision = engine.evaluate_request(analyst_request, results)
    assert "c1" in decision.allowed_chunks
    assert "c2" in decision.denied_chunks
    
    # 2. Scenario: Admin / Research intent -> Should see ALL
    admin_request = AccessRequest(
        principal=Principal(id="u2", tenant_id="t1", roles=["admin"], classifications=["secret"]),
        intent="research",
        query="analyze secrets"
    )
    decision = engine.evaluate_request(admin_request, results)
    assert "c1" in decision.allowed_chunks
    assert "c2" in decision.allowed_chunks

    # 3. Scenario: Admin / Treatment intent (Explicit Deny for Secrets)
    deny_request = AccessRequest(
        principal=Principal(id="u2", tenant_id="t1", roles=["admin"], classifications=["secret"]),
        intent="treatment",
        query="view confidential case"
    )
    decision = engine.evaluate_request(deny_request, results)
    assert "c2" in decision.denied_chunks # Denied by intent-based classification gate

def test_audit_tamper_nuance(tmp_path):
    """
    Sovereign Certification: Prove that --tip misses deep mutations.
    'Shortcuts may support operations; only full verification supports claims.'
    """
    log_path = tmp_path / "cert_audit.jsonl"
    logger = AuditLogger(str(log_path))
    
    # 1. Create a chain of 5 records
    for i in range(5):
        rec = AuditRecord(
            event_id=f"evt-{i}",
            principal="system",
            query_hash="hash",
            query_preview="query",
            decision={"action": "allow", "reason": "OK"},
            candidate_count=1,
            allowed_count=1,
            denied_count=0
        )
        logger.log(rec)
        
    # 2. Verify: Full vs Tip (Both should pass initially)
    valid_full, _ = logger.verify_integrity(full=True)
    valid_tip, _ = logger.verify_integrity(full=False)
    assert valid_full and valid_tip
    
    # 3. TAMPER: Mutate a record in the MIDDLE (record 2)
    with open(log_path, "r") as f:
        lines = f.readlines()
    
    data = json.loads(lines[2])
    data["principal"] = "malicious-actor"
    lines[2] = json.dumps(data) + "\n"
    
    with open(log_path, "w") as f:
        f.writelines(lines)
        
    # 4. Certification Proof: 
    # TIP check should MISS this (it only stays on the last entry)
    # FULL check should CATCH this.
    is_valid_tip, msg_tip = logger.verify_integrity(full=False)
    is_valid_full, msg_full = logger.verify_integrity(full=True)
    
    assert is_valid_tip is True  # TIP check is an operational shortcut
    assert is_valid_full is False # FULL check is the authoritative sovereign claim
    assert "Tampering detected" in msg_full

def test_keyring_fallback_diagnostics():
    """
    Sovereign Certification: Verify graceful fallback when OS enclave is unavailable.
    """
    # 1. Mock keyring failure (Missing Backend)
    with patch("local_rag.audit.KeyringProvider") as mock_prov:
        mock_prov.return_value.get_status.return_value = {
            "type": "keyring",
            "available": False,
            "backend": "Mirror (None)"
        }
        
        logger = AuditLogger()
        status = logger.get_provider_status()
        assert status["available"] is False
        assert status["backend"] == "Mirror (None)"
        
    # 2. Mock 'None' Keying (Headless environment status)
    with patch("local_rag.audit.KeyringProvider") as mock_prov:
        mock_prov.return_value.get_status.return_value = {
            "type": "keyring",
            "available": False,
            "status": "Degraded: Headless Platform"
        }
        logger = AuditLogger()
        assert "Degraded" in logger.get_provider_status().get("status", "")
