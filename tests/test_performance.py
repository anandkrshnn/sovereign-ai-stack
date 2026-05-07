import pytest
import time
import asyncio
from sovereign_ai.pipeline import SovereignPipeline, Config
from sovereign_ai.common.audit import SignedAuditChain

@pytest.mark.benchmark
def test_pipeline_latency_gate(benchmark):
    """
    Performance Gate: Ensure retrieval + gating path stays under latency targets.
    Target: p95 < 150ms
    """
    config = Config(tenant_id="test_perf", principal="analyst")
    pipeline = SovereignPipeline(config)
    query = "What is the recommended treatment protocol for hypertension?"

    latencies = []

    def run_pipeline():
        # We need a synchronous wrapper for the benchmark tool
        loop = asyncio.new_event_loop()
        try:
            start = time.perf_counter()
            loop.run_until_complete(pipeline.ask(query))
            latencies.append(time.perf_counter() - start)
        finally:
            loop.close()

    # Run benchmark
    benchmark.pedantic(run_pipeline, iterations=1, rounds=20)
    
    # Enforce p95 gate
    if latencies:
        latencies.sort()
        p95_idx = int(len(latencies) * 0.95)
        p95_ms = latencies[p95_idx] * 1000
        print(f"\nMeasured p95 Latency: {p95_ms:.2f} ms")
        assert p95_ms < 150, f"Performance regression: p95 latency {p95_ms:.2f}ms exceeds 150ms gate"

@pytest.mark.benchmark
def test_audit_signing_latency(benchmark, tmp_path):
    """
    Performance Gate: Forensic signing must be efficient.
    Target: < 50ms per signature
    """
    audit_file = tmp_path / "perf_audit.jsonl"
    chain = SignedAuditChain(tenant_id="perf_test", audit_file=str(audit_file))
    
    latencies = []

    def sign_event():
        start = time.perf_counter()
        chain.log_event(
            component="test",
            action="perf_check",
            principal="system",
            event_data={"metric": "latency", "value": 1.0}
        )
        latencies.append(time.perf_counter() - start)
        
    benchmark.pedantic(sign_event, iterations=1, rounds=50)
    
    if latencies:
        avg_ms = (sum(latencies) / len(latencies)) * 1000
        print(f"\nMeasured Average Signing Latency: {avg_ms:.2f} ms")
        assert avg_ms < 50, f"Audit signing too slow: {avg_ms:.2f}ms"
