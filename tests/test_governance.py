import pytest
import yaml
import json
from pathlib import Path
from local_rag.policy import PolicyEngine
from local_rag.schemas import SearchResult
from local_rag.audit import AuditLogger
from local_rag.governed import GovernedRetriever

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
        "version": "1",
        "principal": "test-analyst",
        "allow": {
            "classifications": ["public"],
            "tenants": ["tenant-a"]
        },
        "deny": {
            "departments": ["hr"]
        },
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
    decision = engine.enforce("test query", mock_results)
    
    # Expected: 
    # c1: ALLOW (public, tenant-a, not hr)
    # c2: DENY (secret, also hr)
    # c3: DENY (tenant-b)
    
    assert decision.action == "allow"
    assert "c1" in decision.allowed_chunks
    assert "c2" in decision.denied_chunks
    assert "c3" in decision.denied_chunks
    assert len(decision.allowed_chunks) == 1

def test_audit_logging(tmp_path, policy_file, mock_results):
    audit_file = tmp_path / "audit.jsonl"
    logger = AuditLogger(str(audit_file))
    
    # Create a GovernedRetriever manually or use its logic
    # Here we test logger directly for isolation
    from local_rag.schemas import AuditRecord, PolicyDecision
    import uuid
    from datetime import datetime
    
    decision = PolicyDecision(action="allow", reason="Tested", allowed_chunks=["c1"], denied_chunks=["c2"])
    record = AuditRecord(
        event_id=str(uuid.uuid4()),
        principal="test-user",
        query_hash="hash123",
        query_preview="hello",
        decision=decision,
        candidate_count=2,
        allowed_count=1,
        denied_count=1
    )
    
    logger.log(record)
    
    # Verify file content
    assert audit_file.exists()
    logs = logger.read_logs()
    assert len(logs) == 1
    assert logs[0].principal == "test-user"
    assert logs[0].decision.action == "allow"

def test_governed_retriever_airlock(tmp_path, policy_file):
    # Setup a dummy DB for the retriever
    db_path = tmp_path / "test_airlock.db"
    
    # We can't easily ingest into real FTS5 without a real DB setup,
    # but we can mock the internal FTS5Retriever to test the Airlock wrapper
    from unittest.mock import MagicMock
    
    with MagicMock() as mock_fts:
        mock_fts.search.return_value = [
            SearchResult(doc_id="d1", chunk_id="c1", text="text", score=0.9, metadata={"classification": "secret"})
        ]
        
        # Patch the FTS5Retriever inside GovernedRetriever
        from local_rag.governed import GovernedRetriever
        import local_rag.governed
        
        # patches the FTS5Retriever inside GovernedRetriever to avoid real DB init
        original_init = local_rag.governed.FTS5Retriever.__init__
        local_rag.governed.FTS5Retriever.__init__ = lambda *args, **kwargs: None
        
        retriever = GovernedRetriever(str(db_path), policy_file, principal="attacker")
        retriever.retriever = mock_fts # Inject mock
        
        results, decision = retriever.search("gimme secrets")
        
        # Policy in policy_file only allows "public"
        assert len(results) == 0
        assert decision.action == "deny"
        
        # Restore init
        local_rag.governed.FTS5Retriever.__init__ = original_init
