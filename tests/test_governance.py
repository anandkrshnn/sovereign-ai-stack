import pytest
import yaml
import json
import os
from pathlib import Path
from sovereign_ai.rag.policy import PolicyEngine, Principal, AccessRequest
from sovereign_ai.rag.schemas import SearchResult, PolicyDecision
from sovereign_ai.common.audit import SovereignAuditLogger, Principal as AuditPrincipal

@pytest.fixture
def mock_results():
    return [
        SearchResult(
            doc_id="doc-public",
            chunk_id="c1",
            text="Public info",
            score=0.9,
            metadata={"classification": "public", "department": "finance", "tenant_id": "tenant-a"}
        ),
        SearchResult(
            doc_id="doc-secret",
            chunk_id="c2",
            text="Secret info",
            score=0.8,
            metadata={"classification": "secret", "department": "hr", "tenant_id": "tenant-a"}
        ),
        SearchResult(
            doc_id="doc-other-tenant",
            chunk_id="c3",
            text="Private tenant info",
            score=0.7,
            metadata={"classification": "public", "department": "finance", "tenant_id": "tenant-b"}
        )
    ]

@pytest.fixture
def policy_file(tmp_path):
    policy_path = tmp_path / "test_policy.yaml"
    policy_data = {
        "version": "1.0.0-GA",
        "allow": [
            {
                "classifications": ["public"],
                "roles": ["analyst"]
            }
        ],
        "deny": [
            {
                "departments": ["hr"]
            }
        ],
        "limits": {
            "max_results": 2,
            "min_score": 0.5
        }
    }
    with open(policy_path, "w") as f:
        yaml.dump(policy_data, f)
    return str(policy_path)

def test_policy_engine_enforcement(policy_file, mock_results):
    engine = PolicyEngine(policy_file)
    principal = Principal(id="test-analyst", tenant_id="tenant-a", roles=["analyst"], classifications=["public"])
    request = AccessRequest(principal=principal, intent="research", query="test query")
    
    decision = engine.evaluate_request(request, mock_results)
    
    # Expected: 
    # c1: ALLOW (public, tenant-a, analyst role)
    # c2: DENY (secret, not in allowed classifications)
    # c3: DENY (tenant-b mismatch)
    
    assert decision.action == "allow"
    assert "c1" in decision.allowed_chunks
    assert "c2" in decision.denied_chunks
    assert "c3" in decision.denied_chunks
    assert len(decision.allowed_chunks) == 1

def test_audit_logging(tmp_path):
    # SovereignAuditLogger uses base_dir/tenant_id/audit structure
    logger = SovereignAuditLogger(base_dir=str(tmp_path), tenant_id="tenant_alpha")
    
    principal = AuditPrincipal(id="test-user", tenant_id="tenant_alpha")
    data = {"query": "hello", "decision": "allow"}
    
    logger.log("test_event", principal, data)
    
    # Verify file content
    log_file = tmp_path / "tenant_alpha" / "audit" / "sovereign_audit.jsonl"
    assert log_file.exists()
    
    with open(log_file, "r") as f:
        log_entry = json.loads(f.readline())
        assert log_entry["event_type"] == "test_event"
        assert log_entry["principal"]["id"] == "test-user"
        assert log_entry["data"]["query"] == "hello"

def test_governed_retriever_airlock(tmp_path, policy_file):
    # Setup a dummy DB for the retriever
    db_path = tmp_path / "data" / "tenant-a" / "vault" / "sovereign.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    from unittest.mock import MagicMock, patch
    
    with patch("sovereign_ai.rag.governed.FTS5Retriever") as mock_fts_cls:
        mock_fts = mock_fts_cls.return_value
        mock_fts.search.return_value = [
            SearchResult(doc_id="d1", chunk_id="c1", text="secret text", score=0.9, 
                        metadata={"classification": "secret", "tenant_id": "tenant-a"})
        ]
        
        from sovereign_ai.rag.governed import GovernedRetriever
        
        # Policy in policy_file only allows "public" for "analyst" role
        retriever = GovernedRetriever(str(db_path), policy_file, principal="analyst", tenant_id="tenant-a", roles=["analyst"])
        
        results, decision = retriever.search("gimme secrets")
        
        assert len(results) == 0
        assert decision.action == "deny"
        assert "c1" in decision.denied_chunks
