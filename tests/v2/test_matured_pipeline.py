import asyncio

import pytest

from sovereign_ai.pipeline import Config, SovereignPipeline
from sovereign_ai.rag.schemas import Document


@pytest.mark.asyncio
async def test_matured_pipeline_calibration():
    # Setup config with verification
    config = Config(
        tenant_id="test-calibration",
        enable_verification=True,
        fail_closed=False,  # Don't block for this test
    )

    # Initialize pipeline
    pipeline = SovereignPipeline(config)

    # Check if evaluator has calibrator
    assert pipeline._evaluator is not None
    assert pipeline._evaluator.calibrator is not None
    print(
        f"Evaluator calibrator: {pipeline._evaluator.calibrator.A}, {pipeline._evaluator.calibrator.B}"
    )

    # Run a dummy evaluation
    res = pipeline._evaluator.evaluate(
        "What is RAG?", "RAG is Retrieval-Augmented Generation.", "RAG is a type of AI."
    )
    assert "raw_scores" in res
    print(f"Calibrated Grounding: {res['grounding_score']}, Raw: {res['raw_scores'][0]}")

    await pipeline.close()


@pytest.mark.asyncio
async def test_pipeline_policy_certificate():
    import os

    audit_file = "test_audit_cert.jsonl"
    if os.path.exists(audit_file):
        os.remove(audit_file)

    # We use a lower-level test to trigger Merkle checkpoint
    from sovereign_ai.common.audit import SignedAuditChain

    chain = SignedAuditChain(tenant_id="test-cert", audit_file=audit_file)
    chain.checkpoint_interval = 2  # Small interval for testing

    # Log some events to trigger checkpoint
    for i in range(3):
        chain.log_event("comp", "act", "user", {"data": i})

    chain.close()

    # Check logs for policy certificate
    logs = chain.read_logs()
    checkpoints = [l for l in logs if l["action"] == "MERKLE_CHECKPOINT"]

    assert len(checkpoints) > 0
    cert = checkpoints[0]["event_data"].get("policy_safety_cert")
    assert cert is not None
    assert cert["verified"] is True
    assert "engine" in cert
    print(f"Policy Safety Cert found: {cert}")

    if os.path.exists(audit_file):
        os.remove(audit_file)
    if os.path.exists(audit_file + ".checkpoint"):
        os.remove(audit_file + ".checkpoint")


if __name__ == "__main__":
    asyncio.run(test_matured_pipeline_calibration())
    asyncio.run(test_pipeline_policy_certificate())
    print("Matured Pipeline Integration Tests Passed!")
