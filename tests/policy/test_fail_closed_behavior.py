import pytest
import asyncio
from sovereign_ai.rag.pipeline import SovereignPipeline, Config
from sovereign_ai.rag.schemas import Document

@pytest.mark.asyncio
@pytest.mark.sovereign(id="POL-001")
async def test_policy_fail_closed_missing_roles(sovereign_test_env, tmp_path):
    """POL-001: Query with missing role_required should fail-closed."""
    # 1. Create a policy that requires 'admin' role for 'secret' classification
    policy_path = tmp_path / "strict_policy.yaml"
    import yaml
    with open(policy_path, "w") as f:
        yaml.dump({
            "version": "1.0.0-GA",
            "allow": [
                {"roles": ["admin"], "classifications": ["secret"]}
            ],
            "deny": []
        }, f)
        
    alpha_cfg = sovereign_test_env["tenants"]["tenant_alpha"]["config"]
    alpha_cfg.policy_path = str(policy_path)
    alpha_cfg.roles = ["analyst"] # Missing 'admin'!
    
    pipe = SovereignPipeline(alpha_cfg)
    
    # Ingest secret doc
    doc = Document(doc_id="s1", source="internal", content="The key is 123", metadata={"classification": "secret", "tenant_id": "tenant_alpha"})
    await pipe.ingest([doc])
    
    # 2. Query
    response = await pipe.ask("what is the key?")
    
    # PASS CRITERION: Fail-closed response
    assert "[Sovereign Access Denied]" in response.answer
    assert len(response.sources) == 0
    await pipe.close()

@pytest.mark.asyncio
@pytest.mark.sovereign(id="POL-004")
async def test_secret_scanner_guardrail(sovereign_test_env):
    """POL-004: SecretScanner must detect and flag credentials in chunks."""
    from sovereign_ai.rag.utils import contains_secret
    
    # 1. Test strings with various credentials
    valid_text = "The revenue is $50M."
    invalid_text = "The AWS key is AKIA1234567890ABCDEF."
    invalid_text_2 = "My OpenAI key: sk-U7f8g9h0j1k2l3m4n5o6p7q8r9s0t1"
    
    # 2. PASS CRITERION: Regex detection
    assert contains_secret(valid_text) is False
    assert contains_secret(invalid_text) is True
    assert contains_secret(invalid_text_2) is True
    
    # 3. Integration Check: Ingesting a secret should (ideally) be flagged or excluded
    # In this GA version, we assume retriever/engine calls contains_secret at ingestion
    # For now, we just verify the utility is functional for the policy engine to use.
