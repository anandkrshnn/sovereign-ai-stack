import pytest
import asyncio
from sovereign_ai import SovereignPipeline, Config
from sovereign_ai.rag.schemas import Document

@pytest.mark.asyncio
@pytest.mark.sovereign(id="ISO-001")
async def test_cross_tenant_query_leakage(sovereign_test_env):
    """ISO-001: Query tenant_alpha DB with tenant_beta principal must return zero results."""
    # 1. Setup Data in Alpha
    alpha_cfg = sovereign_test_env["tenants"]["tenant_alpha"]["config"]
    alpha_pipe = SovereignPipeline(alpha_cfg)
    
    # Ingest document into Alpha's private DB
    doc = Document(
        doc_id="alpha-secret", 
        source="internal",
        content="Alpha's private quarterly target is $50M.",
        metadata={"tenant_id": "tenant_alpha", "classification": "confidential"}
    )
    await alpha_pipe.ingest([doc])
    
    # 2. Attack: Query from Beta's perspective
    beta_cfg = sovereign_test_env["tenants"]["tenant_beta"]["config"]
    # We point Beta's config to Alpha's DB path to simulate an "Airlock Bypass" attempt
    beta_cfg.db_path = alpha_cfg.db_path 
    beta_pipe = SovereignPipeline(beta_cfg)
    
    # Query with Beta's principal identity
    results = await beta_pipe.ask("what is the revenue target?", intent="research")
    
    # 3. PASS CRITERION: Zero authorized results
    assert "Alpha's private" not in results.answer
    assert len(results.sources) == 0
    await alpha_pipe.close()
    await beta_pipe.close()

@pytest.mark.asyncio
@pytest.mark.sovereign(id="ISO-002")
async def test_identical_text_collision_scoping(sovereign_test_env):
    """ISO-002: Identical text across tenants must be scoped correctly."""
    # 1. Ingest same text into Alpha and Beta
    content = "The target is 100 units."
    
    for tid in ["tenant_alpha", "tenant_beta"]:
        cfg = sovereign_test_env["tenants"][tid]["config"]
        pipe = SovereignPipeline(cfg)
        doc = Document(doc_id=f"{tid}-doc", source="shared", content=content, metadata={"tenant_id": tid})
        await pipe.ingest([doc])
        await pipe.close()
        
    # 2. Query as Beta
    beta_cfg = sovereign_test_env["tenants"]["tenant_beta"]["config"]
    beta_pipe = SovereignPipeline(beta_cfg)
    response = await beta_pipe.ask("what is the target?")
    
    # PASS CRITERION: Sources must strictly belong to Beta
    assert len(response.sources) > 0
    for s in response.sources:
        assert s.metadata["tenant_id"] == "tenant_beta"
    await beta_pipe.close()

@pytest.mark.asyncio
@pytest.mark.sovereign(id="ISO-004")
async def test_metadata_poisoning_injection(sovereign_test_env):
    """ISO-004: Malformed/Poisoned tenant_id in query should be blocked."""
    alpha_cfg = sovereign_test_env["tenants"]["tenant_alpha"]["config"]
    alpha_pipe = SovereignPipeline(alpha_cfg)
    
    # Attempt SQL Injection through principal tenant_id
    poisoned_cfg = Config(
        db_path=alpha_cfg.db_path,
        tenant_id="tenant_alpha' OR '1'='1",
        principal="attacker",
        use_cache=False
    )
    poison_pipe = SovereignPipeline(poisoned_cfg)
    
    response = await poison_pipe.ask("get all docs")
    
    # PASS CRITERION: Zero results due to sanitization / mismatch
    assert len(response.sources) == 0
    await alpha_pipe.close()
    await poison_pipe.close()
