import pytest
import json
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from sovereign_ai.agent.reasoning import SovereignReasoningLoop
from sovereign_ai.agent.orchestrator import SovereignAgent
from sovereign_ai.agent.schemas import AgentState, VerifyFailSignal, SecurityHalt

@pytest.fixture
def mock_orchestrator():
    orchestrator = MagicMock(spec=SovereignAgent)
    orchestrator.execute_tool = AsyncMock()
    return orchestrator

@pytest.fixture
def loop(mock_orchestrator):
    return SovereignReasoningLoop(mock_orchestrator)

@pytest.mark.asyncio
async def test_reasoning_loop_success(loop, mock_orchestrator):
    """Verify a successful ReAct loop with a tool call and final answer."""
    state = AgentState(principal_id="user1")
    
    # Mock LLM responses: 1. Tool Call, 2. Final Answer
    responses = [
        'Thought: I need to read the file.\nAction: read_file({"path": "test.txt"})',
        'Final Answer: The file contains hello world.'
    ]
    
    with patch.object(loop, '_call_llm', side_effect=responses):
        mock_orchestrator.execute_tool.return_value = "hello world"
        
        result = await loop.chat("What is in the file?", state)
        
        from unittest.mock import ANY
        assert result == "The file contains hello world."
        mock_orchestrator.execute_tool.assert_awaited_once_with(
            "read_file", {"path": "test.txt"}, state, "", context_version=ANY
        )

@pytest.mark.asyncio
async def test_reasoning_loop_security_halt(loop, mock_orchestrator):
    """Verify that a VerifyFailSignal from the orchestrator halts the reasoning loop."""
    state = AgentState(principal_id="user1")
    
    responses = [
        'Thought: I will write a malicious file.\nAction: write_file({"path": "shell.sh", "content": "rm -rf /"})'
    ]
    
    with patch.object(loop, '_call_llm', side_effect=responses):
        mock_orchestrator.execute_tool.side_effect = VerifyFailSignal(
            failure_type="GROUNDING_ERROR",
            action_id="123",
            retry_count=0,
            signed_failure_hash="hash123"
        )
        
        result = await loop.chat("Write a shell script.", state)
        
        assert "SECURITY_HALT" in result
        assert "hash123" in result
        # The loop should terminate immediately
        assert loop.max_iterations > 1 

@pytest.mark.asyncio
async def test_reasoning_loop_security_denial(loop, mock_orchestrator):
    """Verify that a SecurityHalt (ABAC/Idempotency) from the orchestrator halts the reasoning loop."""
    state = AgentState(principal_id="user1")
    
    responses = [
        'Thought: I will access a restricted file.\nAction: read_file({"path": "/etc/shadow"})'
    ]
    
    with patch.object(loop, '_call_llm', side_effect=responses):
        mock_orchestrator.execute_tool.side_effect = SecurityHalt("Policy denial: restricted path")
        
        result = await loop.chat("Read shadow file.", state)
        
        assert "SECURITY_DENIAL" in result
        assert "Policy denial" in result
