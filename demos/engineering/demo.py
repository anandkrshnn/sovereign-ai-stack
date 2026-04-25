import asyncio
from local_rag import RAGPipeline, Config

async def run_demo():
    print("\n[ENGINEERING SCENARIO] Config Privacy")
    
    # Get the directory of the current script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    policy_path = os.path.join(base_dir, "policy.yaml")

    # Scenario 1: Admin requesting deployment config
    cfg_admin = Config(
        db_path="demos/engineering/eng.db",
        policy_path=policy_path,
        tenant_id="eng_team",
        roles=["admin"]
    )
    pipe_admin = RAGPipeline(cfg_admin)
    res_admin = await pipe_admin.ask("Production image version?")
    print(f"PASS: Admin Access: {'ALLOWED' if res_admin.sources else 'DENIED'}")
    await pipe_admin.close()

    # Scenario 2: Developer requesting production credentials
    cfg_dev = Config(
        db_path="demos/engineering/eng.db",
        policy_path=policy_path,
        tenant_id="eng_team",
        roles=["developer"]
    )
    pipe_dev = RAGPipeline(cfg_dev)
    res_dev = await pipe_dev.ask("AWS production credentials?")
    print(f"BLOCK: Developer Access: {'LEAKED' if res_dev.sources else 'BLOCKED (Sovereign Fail-Closed)'}")
    await pipe_dev.close()

if __name__ == "__main__":
    asyncio.run(run_demo())
