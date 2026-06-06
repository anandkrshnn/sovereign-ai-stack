import asyncio

import pytest

from sovereign_ai.common.ledger_db import DatabaseAuditChain


@pytest.mark.asyncio
async def test_database_ledger_append_and_proof():
    # Use in-memory SQLite for testing
    ledger = DatabaseAuditChain("test-tenant", "sqlite+aiosqlite:///:memory:")
    await ledger.initialize()

    # Append a few records
    for i in range(15):
        await ledger.append_record(f"ACTION_{i}", {"data": f"value_{i}"})

    # Since checkpoint interval is 10, record 5 should be sealed by checkpoint at 10.
    proof = await ledger.get_audit_proof(5)

    assert "leaf_hash" in proof
    assert "root_hash" in proof
    assert "proof" in proof

    # Also test record 12, which is not yet checkpointed. It should force a checkpoint.
    proof2 = await ledger.get_audit_proof(12)
    assert "leaf_hash" in proof2

    is_valid = await ledger.verify_chain()
    assert is_valid is True
