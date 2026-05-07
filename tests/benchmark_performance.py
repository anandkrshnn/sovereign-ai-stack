import asyncio
import time
import os
import shutil
from pathlib import Path
from sovereign_ai import SovereignPipeline, Config, Document

async def run_performance_benchmark():
    print("Starting Sovereign AI Performance Benchmark...")
    
    # 1. Setup Environment
    base_dir = Path("bench_env")
    if base_dir.exists():
        shutil.rmtree(base_dir)
    base_dir.mkdir()
    
    cfg = Config(
        db_path=str(base_dir / "sovereign.db"),
        policy_path=None, 
        tenant_id="bench_tenant",
        principal="admin",
        enable_verification=True
    )
    
    pipeline = SovereignPipeline(cfg)
    
    # 2. Ingest Data
    print("Ingesting benchmark corpus...")
    docs = [
        Document(doc_id=f"doc_{i}", source="bench", content=f"Secret key for level {i} is {os.urandom(8).hex()}", tenant_id="bench_tenant")
        for i in range(10)
    ]
    await pipeline.ingest(docs)
    
    # 3. Concurrent Requests
    print("Executing 50 concurrent requests...")
    start_time = time.time()
    
    async def single_request(i):
        return await pipeline.ask(f"What is the secret key for level {i%10}?")

    tasks = [single_request(i) for i in range(50)]
    results = await asyncio.gather(*tasks)
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # 4. Results Summary
    print(f"\nBenchmark Results:")
    print(f"Total time for 50 requests: {total_time:.2f}s")
    print(f"Throughput: {50/total_time:.2f} RPS")
    
    # 5. Audit Integrity
    print("\nVerifying Audit Integrity...")
    from sovereign_ai.common.audit import SovereignAuditLogger
    auditor = SovereignAuditLogger(base_dir=str(base_dir), tenant_id="bench_tenant")
    is_valid = auditor.verify_integrity()
    
    if is_valid:
        print("Audit Integrity: VERIFIED")
    else:
        print("Audit Integrity: FAILED")
        exit(1)

    await pipeline.close()

if __name__ == "__main__":
    asyncio.run(run_performance_benchmark())
