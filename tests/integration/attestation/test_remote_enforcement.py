import asyncio
import pytest
from sovereign_ai.pipeline import SovereignPipeline, Config
from sovereign_ai.common.schemas import SecurityHalt

@pytest.mark.asyncio
async def test_remote_attestation_enforcement_missing_url():
    """Verify that the pipeline halts if remote attestation is required but no URL is provided."""
    config = Config(
        tenant_id="test-tenant",
        require_remote_attestation=True,
        remote_verifier_url=None
    )
    
    with pytest.raises(SecurityHalt) as excinfo:
        SovereignPipeline(config)
    
    assert "remote_verifier_url required" in str(excinfo.value)

@pytest.mark.asyncio
async def test_remote_attestation_enforcement_unreachable():
    """Verify that the pipeline halts if the remote verifier is unreachable."""
    config = Config(
        tenant_id="test-tenant",
        require_remote_attestation=True,
        remote_verifier_url="http://localhost:9999", # Non-existent
        fail_closed=True
    )
    
    # This will attempt a real network call
    with pytest.raises(SecurityHalt) as excinfo:
        # We use a separate thread or just run it because __init__ triggers it
        SovereignPipeline(config)
    
    assert "Verifier Unreachable" in str(excinfo.value)

if __name__ == "__main__":
    # Quick manual run
    async def run_manual():
        print("Running manual enforcement test...")
        config = Config(require_remote_attestation=True, remote_verifier_url="http://localhost:9999")
        try:
            SovereignPipeline(config)
        except SecurityHalt as e:
            print(f"Caught expected Halt: {e}")
            
    asyncio.run(run_manual())
