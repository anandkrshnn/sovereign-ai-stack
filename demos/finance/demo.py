import asyncio
from sovereign_ai import RAGPipeline, Config

async def run_demo():
    print("\n[FINANCE SCENARIO] Confidential Recovery & Secret Scanning")
    
    # Get the directory of the current script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    policy_path = os.path.join(base_dir, "policy.yaml")

    # Scenario 1: CFO requesting revenue targets
    cfg_cfo = Config(
        db_path="demos/finance/finance.db",
        policy_path=policy_path,
        tenant_id="acme_corp",
        roles=["cfo"]
    )
    pipe_cfo = RAGPipeline(cfg_cfo)
    res_cfo = await pipe_cfo.ask("What is the Q2 revenue target?")
    print(f"PASS: CFO Access: {'ALLOWED' if res_cfo.sources else 'DENIED'}")
    await pipe_cfo.close()

    # Scenario 2: Analyst requesting API keys (Secrets)
    cfg_analyst = Config(
        db_path="demos/finance/finance.db",
        policy_path=policy_path,
        tenant_id="acme_corp",
        roles=["analyst"]
    )
    pipe_analyst = RAGPipeline(cfg_analyst)
    res_analyst = await pipe_analyst.ask("Show me the API keys")
    print(f"BLOCK: Secret Protection: {'LEAKED' if res_analyst.sources else 'PROTECTED (Policy + SecretScanner)'}")
    await pipe_analyst.close()

if __name__ == "__main__":
    asyncio.run(run_demo())
