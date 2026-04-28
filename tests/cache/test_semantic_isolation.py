import pytest
import asyncio
from sovereign_ai import SovereignPipeline, Config
from sovereign_ai.rag.schemas import Document, RAGResponse

@pytest.mark.asyncio
@pytest.mark.sovereign(id="CAC-001")
async def test_semantic_cache_tenant_isolation(sovereign_test_env):
    """CAC-001: Cache results from tenant_alpha must NOT leak to tenant_beta."""
    alpha_cfg = sovereign_test_env["tenants"]["tenant_alpha"]["config"]
    beta_cfg = sovereign_test_env["tenants"]["tenant_beta"]["config"]
    
    # 1. Warm up cache for Alpha
    alpha_pipe = SovereignPipeline(alpha_cfg)
    query = "what is the revenue target?"
    
    # Inject a fake response directly into Alpha's cache
    mock_res = RAGResponse(answer="Alpha's private answer.", sources=[], model_name="test")
    await alpha_pipe._engine.cache.set(query, mock_res, tenant_id="tenant_alpha")
    
    # 2. Check Beta's cache for the same query
    beta_pipe = SovereignPipeline(beta_cfg)
    # Since they share the same cache DIR by default in tests (tmp_path), 
    # we verify that the tenant_id 'where' clause works.
    beta_hit = await beta_pipe._engine.cache.get(query, tenant_id="tenant_beta")
    
    # PASS CRITERION: Beta should not hit Alpha's cache entry
    assert beta_hit is None
    
    # 3. Double check Alpha DOES hit it
    alpha_hit = await alpha_pipe._engine.cache.get(query, tenant_id="tenant_alpha")
    assert alpha_hit is not None
    assert alpha_hit.answer == "Alpha's private answer."
    
    await alpha_pipe.close()
    await beta_pipe.close()
