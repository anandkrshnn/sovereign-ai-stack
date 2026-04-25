import asyncio
import sys
import os

# Add monorepo to path if needed
sys.path.append(os.getcwd())

from sovereign_ai import SovereignPipeline, Config

async def run_test():
    print("Running Test 1: Verify the Hard Gate...")
    
    # Create pipeline with medical content
    text = "Patient Protocol: Hypertension management requires monitoring BP daily. Medication A is prescribed for Stage 1."
    
    config = Config(enable_verification=True, fail_closed=True)
    pipeline = SovereignPipeline(config)
    
    # Ingest content
    from sovereign_ai.rag.schemas import Document
    doc = Document(doc_id="d1", source="protocol.txt", content=text, tenant_id="default")
    await pipeline.ingest([doc])
    
    # Case A: Good question (grounded)
    print("\n[Case A] Grounded Query: 'How do I manage hypertension?'")
    res_a = await pipeline.ask("How do I manage hypertension?")
    print(f"Answer: {res_a.answer}")
    score = res_a.metadata.get("verification", {}).get("overall_score", 0)
    print(f"Verification Score: {score}")
    
    # Case B: Irrelevant question (hallucination risk)
    print("\n[Case B] Irrelevant Query: 'What is the capital of France?'")
    res_b = await pipeline.ask("What is the capital of France?")
    print(f"Answer: {res_b.answer}")
    score_b = res_b.metadata.get("verification", {}).get("overall_score", 0)
    print(f"Verification Score: {score_b}")
    
    if "[Sovereign Access Denied]" in res_b.answer:
        print("\n✅ Test 1 PASSED: Hard Gate blocked irrelevant answer.")
    else:
        print("\n❌ Test 1 FAILED: Hard Gate allowed ungrounded answer.")

    await pipeline.close()

if __name__ == "__main__":
    asyncio.run(run_test())
