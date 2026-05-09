import asyncio
import json
from pathlib import Path
from sovereign_ai.pipeline import SovereignPipeline, Config
from sovereign_ai.rag.schemas import Document

async def main():
    # 1. Initialize Pipeline with Attestation Enabled
    config = Config(
        tenant_id="test_tenant",
        enable_attestation=True
    )
    pipeline = SovereignPipeline(config)
    
    # 2. Ingest some data to trigger events
    doc = Document(
        doc_id="test-1",
        content="Hardware attestation test content.",
        source="manual",
        tenant_id="test_tenant"
    )
    await pipeline.ingest([doc])
    
    # 3. Ask a question (triggers audit events)
    await pipeline.ask("What is hardware attestation?")
    
    # 4. Flush the audit chain to trigger a Merkle Checkpoint
    # By default, MERKLE_BLOCK_SIZE is 100, but we can force it or wait.
    # In audit.py, SignedAuditChain._finalize_merkle_block is called when event_buffer >= MERKLE_BLOCK_SIZE or on close.
    await pipeline.close()
    
    # 5. Inspect the audit log for the MERKLE_CHECKPOINT event
    log_path = Path("data/test_tenant/audit/sovereign_audit.jsonl")
    if not log_path.exists():
        print("Error: Audit log not found.")
        return
        
    print("\n--- Audit Log Inspection ---")
    with open(log_path, "r") as f:
        for line in f:
            event = json.loads(line)
            if event.get("action") == "MERKLE_CHECKPOINT":
                print(f"Found MERKLE_CHECKPOINT!")
                print(f"Merkle Root: {event['event_data']['merkle_root']}")
                quote = event['event_data'].get("attestation_quote")
                if quote:
                    print("✅ Hardware Attestation Quote found in checkpoint!")
                    print(f"Backend: {quote.get('backend')}")
                    print(f"Nonce matches root: {quote.get('nonce') == event['event_data']['merkle_root']}")
                else:
                    print("❌ No hardware attestation quote found in checkpoint.")

if __name__ == "__main__":
    asyncio.run(main())
