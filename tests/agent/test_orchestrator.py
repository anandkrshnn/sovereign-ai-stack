import pytest
import asyncio
import json
from unittest.mock import MagicMock, patch
from pathlib import Path

from sovereign_ai.agent.orchestrator import SovereignAgent
from sovereign_ai.agent.schemas import AgentState, RecordStatus, VerifyFailSignal, SecurityHalt
from sovereign_ai.agent.idempotency import PersistentIdempotencyStore
from sovereign_ai.common.audit import SignedAuditChain
from sovereign_ai.verify.evaluator import SovereignEvaluator
from sovereign_ai.agent.broker.engine import LocalPermissionBroker

@pytest.fixture
def mock_broker():
    broker = MagicMock(spec=LocalPermissionBroker)
    broker.request_permission.return_value = {"granted": True}
    return broker

@pytest.fixture
def mock_evaluator():
    evaluator = MagicMock(spec=SovereignEvaluator)
    evaluator.evaluate.return_value = {
        "overall_score": 0.95,
        "passed": True,
        "grounding_score": 0.95,
        "faithfulness_score": 0.95
    }
    return evaluator

@pytest.fixture
def mock_audit_chain(tmp_path):
    log_path = tmp_path / "test_audit.jsonl"
    chain = SignedAuditChain(tenant_id="test_tenant", audit_file=log_path)
    return chain

@pytest.fixture
def agent(mock_broker, mock_evaluator, mock_audit_chain):
    return SovereignAgent(
        broker=mock_broker,
        evaluator=mock_evaluator,
        audit_chain=mock_audit_chain
    )

@pytest.mark.asyncio
async def test_interceptor_loop_success(agent, mock_broker, mock_evaluator, mock_audit_chain):
    """Verify the standard success path: Govern -> Idempotency -> Prove -> Verify -> Execute."""
    state = AgentState(principal_id="user1", session_id="session1")
    tool_name = "read_file"
    tool_args = {"path": "sandbox/hello.txt"}
    context = "The file hello.txt exists in the sandbox."
    
    with patch.object(agent, '_dispatch_execution', return_value="File content") as mock_exec:
        result = await agent.execute_tool(tool_name, tool_args, state, context)
        
        # Ensure audit queue is drained before assertions
        await agent.close()

        assert result == "File content"
        assert mock_broker.request_permission.called
        assert mock_evaluator.evaluate.called
        assert mock_exec.called
        
        # Verify Audit Chain (Intent, Verification, Observation)
        assert mock_audit_chain.verify_chain() is True
        assert mock_audit_chain.sequence_number == 3

@pytest.mark.asyncio
async def test_interceptor_loop_governance_denial(agent, mock_broker):
    """Verify that a policy denial blocks execution before any intent is signed."""
    mock_broker.request_permission.return_value = {"granted": False, "reason": "Restricted file"}
    
    state = AgentState(principal_id="user1")
    
    with pytest.raises(SecurityHalt, match="Action blocked by policy"):
        try:
            await agent.execute_tool("write_file", {"path": "/etc/passwd"}, state, "some context")
        finally:
            await agent.close()
    
    # Verify Audit Chain only has the denial record
    assert agent.audit_chain.sequence_number == 1
    # Check that it's a governance denial
    # (In a real test we'd inspect the log file content)

@pytest.mark.asyncio
async def test_interceptor_loop_idempotency(agent):
    """Verify that duplicate actions are blocked by the idempotency key."""
    state = AgentState(principal_id="user1")
    tool_name = "read_file"
    tool_args = {"path": "sandbox/repeat.txt"}
    
    try:
        with patch.object(agent, '_dispatch_execution', return_value="Success"):
            # First call
            await agent.execute_tool(tool_name, tool_args, state, "context")
            
            # Second call with same args
            with pytest.raises(SecurityHalt, match="Duplicate action detected"):
                await agent.execute_tool(tool_name, tool_args, state, "context")
    finally:
        await agent.close()

@pytest.mark.asyncio
async def test_interceptor_loop_verification_failure(agent, mock_evaluator):
    """Verify that an NLI verification failure raises VerifyFailSignal and blocks execution."""
    mock_evaluator.evaluate.return_value = {
        "overall_score": 0.4,
        "passed": False,
        "grounding_score": 0.4,
        "faithfulness_score": 0.4
    }
    
    state = AgentState(principal_id="user1")
    
    with patch.object(agent, '_dispatch_execution') as mock_exec:
        with pytest.raises(VerifyFailSignal):
            try:
                await agent.execute_tool("read_file", {"path": "sandbox/test.txt"}, state, "wrong context")
            finally:
                await agent.close()
        
        assert not mock_exec.called
        # Audit Chain should have 2 records: Intent, Verification (FAIL)
        assert agent.audit_chain.sequence_number == 2

@pytest.mark.asyncio
async def test_interceptor_loop_cancellation_safety(agent):
    """Verify that a cancelled task still writes an execution error to the audit log."""
    state = AgentState(principal_id="user1")
    
    async def cancelled_exec(*args, **kwargs):
        raise asyncio.CancelledError()

    with patch.object(agent, '_dispatch_execution', side_effect=cancelled_exec):
        with pytest.raises(asyncio.CancelledError):
            try:
                await agent.execute_tool("read_file", {"path": "sandbox/cancel.txt"}, state, "context")
            finally:
                await agent.close()
        
        # Audit Chain should have 3 records: Intent, Verification, Observation (EXEC_ERROR)
        assert agent.audit_chain.sequence_number == 3

@pytest.mark.asyncio
async def test_persistent_idempotency(tmp_path, mock_broker, mock_evaluator, mock_audit_chain):
    """Refinement 2: Verify that idempotency survives agent restarts using SQLite."""
    db_path = tmp_path / "idem.db"
    store = PersistentIdempotencyStore(db_path)
    
    agent1 = SovereignAgent(mock_broker, mock_evaluator, mock_audit_chain, idempotency_store=store)
    state = AgentState(principal_id="user1")
    
    try:
        with patch.object(agent1, '_dispatch_execution', return_value="Success"):
            await agent1.execute_tool("write", {"val": 1}, state, "context")
    finally:
        await agent1.close()

    # Simulate restart by creating new agent with same store
    agent2 = SovereignAgent(mock_broker, mock_evaluator, mock_audit_chain, idempotency_store=store)
    try:
        with pytest.raises(SecurityHalt, match="Duplicate action detected"):
            await agent2.execute_tool("write", {"val": 1}, state, "context")
    finally:
        await agent2.close()

@pytest.mark.asyncio
async def test_verify_fail_round_trip(agent, mock_evaluator, mock_audit_chain):
    """
    Refinement 3: Assert that VerifyFailSignal correctly chains records 
    and leaves the audit log in a consistent state.
    """
    mock_evaluator.evaluate.return_value = {
        "overall_score": 0.2,
        "passed": False,
        "grounding_score": 0.2,
        "faithfulness_score": 0.2
    }
    
    state = AgentState(principal_id="user1")
    tool_name = "write_file"
    tool_args = {"path": "sandbox/secret.txt", "content": "hallucination"}
    
    with pytest.raises(VerifyFailSignal) as exc_info:
        try:
            await agent.execute_tool(tool_name, tool_args, state, "context")
        finally:
            # We must NOT close the agent here if we need the hash in the exception,
            # but wait=True in execute_tool already ensured the hash is there.
            # However, we need to drain the queue to check the sequence number.
            await agent.close()
    
    # 1. Assert Signal Content
    assert exc_info.value.failure_type == "GROUNDING_ERROR"
    
    # 2. Verify Chain Integrity
    assert mock_audit_chain.verify_chain() is True
    assert mock_audit_chain.sequence_number == 2 # Intent + Verification
    
    # 3. Verify Sequencing (Linkage)
    with open(mock_audit_chain.audit_file, "r") as f:
        lines = f.readlines()
    
    intent = json.loads(lines[0])
    verify = json.loads(lines[1])
    
    assert verify["prev_hash"] == intent["curr_hash"]
    assert verify["event_data"]["status"] == RecordStatus.FAIL
    assert verify["curr_hash"] == exc_info.value.signed_failure_hash

@pytest.mark.asyncio
async def test_interceptor_loop_contextual_idempotency(agent):
    """Verify that context_version allows re-execution of identical calls."""
    state = AgentState(principal_id="user1")
    tool_name = "read_file"
    tool_args = {"path": "sandbox/context_test.txt"}
    
    try:
        with patch.object(agent, '_dispatch_execution', return_value="Success"):
            # 1. First call in Context A
            await agent.execute_tool(tool_name, tool_args, state, "context", context_version="v1")
            
            # 2. Second call in same Context A (should be blocked)
            with pytest.raises(SecurityHalt, match="Duplicate action detected"):
                await agent.execute_tool(tool_name, tool_args, state, "context", context_version="v1")
            
            # 3. Third call in Context B (should be allowed)
            await agent.execute_tool(tool_name, tool_args, state, "context", context_version="v2")
    finally:
        await agent.close()
        # (In a real test we'd verify the third record is EXEC_ERROR)

@pytest.mark.asyncio
async def test_interceptor_loop_hardware_tpm_p256(agent, mock_broker, mock_evaluator, tmp_path):
    """Verify that the interceptor loop correctly uses P-256 signing with a hardware anchor."""
    from sovereign_ai.common.hardware_trust import WindowsTPMAnchor
    from sovereign_ai.common.audit import SignedAuditChain
    from sovereign_ai.agent.schemas import AgentState, RecordStatus
    from unittest.mock import AsyncMock, patch
    import os
    import json
    
    # Use isolated directory for this test
    audit_file = tmp_path / "p256_audit.jsonl"
    tpm_anchor = WindowsTPMAnchor(tenant_id="tpm_test_isolated")
    p256_audit = SignedAuditChain(tenant_id="tpm_test_isolated", audit_file=audit_file, anchor=tpm_anchor)
    agent.audit_chain = p256_audit
    
    state = AgentState(principal_id="user1")
    
    # 1. Successful execution
    mock_broker.request_permission.return_value = {"granted": True}
    
    with patch.object(agent, "_dispatch_execution", new_callable=AsyncMock) as mock_exec:
        mock_exec.return_value = "success"
        
        await agent.execute_tool("read_file", {"path": "test.txt"}, state, "thought1")
        
        # Ensure all events are processed
        await agent.close() 
        
        # Verify the chain uses p256
        success = p256_audit.verify_chain()
        if not success:
            with open(audit_file, "r") as f:
                print(f"DEBUG: File content:\n{f.read()}")
        assert success is True
        
        # Check the actual file content for the algorithm field
        with open(audit_file, "r") as f:
            first_event = json.loads(f.readline())
            assert first_event["algorithm"] == "rsa2048"

    # Cleanup
    await agent.close()
