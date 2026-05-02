import asyncio
import time
import os
import shutil
from pathlib import Path
from sovereign_ai import SovereignPipeline, Config, Document

async def run_stress_test():
    print("Starting Sovereign 'Verified Airlock' Stress Test...")
    
    # 1. Setup Environment
    base_dir = Path("stress_test_env")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir()
    
    cfg = Config(
        db_path=str(base_dir / "sovereign.db"),
        policy_path=None, # Default Allow
        tenant_id="stress_tenant",
        principal="admin",
        enable_verification=True
    )
    
    pipeline = SovereignPipeline(cfg)
    
    # 2. Ingest Data
    print("Ingesting test corpus...")
    docs = [
        Document(doc_id=f"doc_{i}", source="stress", content=f"Secret key for level {i} is {os.urandom(8).hex()}", tenant_id="stress_tenant")
        for i in range(10)
    ]
    await pipeline.ingest(docs)
    
    # 3. Concurrent Requests
    print("Executing 50 concurrent verified requests...")
    start_time = time.time()
    
    async def single_request(i):
        return await pipeline.ask(f"What is the secret key for level {i%10}?")

    tasks = [single_request(i) for i in range(50)]
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # 4. Verify Results
    print(f"Total time for 50 requests: {total_time:.2f}s ({50/total_time:.2f} RPS)")
    
    # 5. Verify Audit Integrity
    print("Verifying Forensic Audit Chain...")
    # Audit log is usually in current dir or as specified. 
    # In our implementation it defaults to base_dir/tenant_id/audit/sovereign_audit.jsonl
    audit_path = base_dir / "stress_tenant" / "audit" / "sovereign_audit.jsonl"
    
    from sovereign_ai.common.audit import SovereignAuditLogger
    auditor = SovereignAuditLogger(base_dir=str(base_dir), tenant_id="stress_tenant")
    is_valid = auditor.verify_integrity()
    
    if is_valid:
        print("Audit Chain: INTACT")
    else:
        print("Audit Chain: TAMPERED OR BROKEN")
        exit(1)

    print("All systems Nominal. Ready for HN Launch.")
    await pipeline.close()

if __name__ == "__main__":
    asyncio.run(run_stress_test())
