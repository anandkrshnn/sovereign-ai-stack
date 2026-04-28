import pytest
import yaml
import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch
from sovereign_ai.rag.policy import PolicyEngine, Principal, AccessRequest
from sovereign_ai.rag.schemas import SearchResult
from sovereign_ai.common.audit import SovereignAuditLogger, Principal as AuditPrincipal

@pytest.fixture
def abac_policy(tmp_path):
    policy_path = tmp_path / "v100_policy.yaml"
    policy_data = {
        "version": "1.0.0-GA",
        "allow": [
            {
                "roles": ["admin"],
                "intents": ["research", "audit"],
                "classifications": ["all"],
                "tenant_id": "any"
            },
            {
                "roles": ["analyst"],
                "intents": ["general"],
                "classifications": ["public", "internal"],
                "tenant_id": "any"
            }
        ],
        "deny": [
            {
                "intents": ["treatment"],
                "classifications": ["secret"],
                "tenant_id": "any"
            }
        ],
        "limits": {"max_results": 10}
    }
    with open(policy_path, "w") as f:
        yaml.dump(policy_data, f)
    return str(policy_path)

def test_abac_matrix_integration(abac_policy):
    """Sovereign Certification: Verify Principal/Intent/Classification matrix."""
    engine = PolicyEngine(abac_policy)
    
    results = [
        SearchResult(doc_id="d1", chunk_id="c1", text="Public", score=0.9, 
                    metadata={"classification": "public", "tenant_id": "t1"}),
        SearchResult(doc_id="d2", chunk_id="c2", text="Secret", score=0.9, 
                    metadata={"classification": "secret", "tenant_id": "t1"}),
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

def test_audit_tamper_detection(tmp_path):
    """Sovereign Certification: Prove detection of audit mutations."""
    logger = SovereignAuditLogger(base_dir=str(tmp_path), tenant_id="t1")
    principal = AuditPrincipal(id="system", tenant_id="t1")
    
    # 1. Create a chain of 3 records
    for i in range(3):
        logger.log("test_event", principal, {"i": i})
        
    # 2. Verify initial integrity
    assert logger.verify_integrity() is True
    
    # 3. TAMPER: Mutate a record in the MIDDLE
    with open(logger.log_path, "r") as f:
        lines = f.readlines()
    
    data = json.loads(lines[1])
    data["data"]["i"] = 999 # Mutate
    lines[1] = json.dumps(data) + "\n"
    
    with open(logger.log_path, "w") as f:
        f.writelines(lines)
        
    # 4. Integrity check should CATCH this
    assert logger.verify_integrity() is False

def test_hardware_binding_fails_on_deletion(tmp_path):
    """Sovereign Certification: Detect deletion via anchor mismatch."""
    logger = SovereignAuditLogger(base_dir=str(tmp_path), tenant_id="t1")
    principal = AuditPrincipal(id="system", tenant_id="t1")
    
    logger.log("evt1", principal, {})
    logger.log("evt2", principal, {})
    
    assert logger.verify_integrity() is True
    
    # TAMPER: Delete the last line
    with open(logger.log_path, "r") as f:
        lines = f.readlines()
    
    with open(logger.log_path, "w") as f:
        f.writelines(lines[:-1]) # Remove last event
        
    # Should FAIL because the log_path's final hash won't match the saved anchor
    assert logger.verify_integrity() is False
