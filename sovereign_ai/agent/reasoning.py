import json
import re
import asyncio
import logging
import httpx
import hashlib
from typing import Dict, Any, List, Optional, Tuple

from .orchestrator import SovereignAgent
from .schemas import AgentState, VerifyFailSignal, SecurityHalt, RecordStatus
from .config import Config

logger = logging.getLogger(__name__)

class SovereignReasoningLoop:
    """
    Advanced ReAct reasoning loop that integrates the hardened SovereignAgent orchestrator.
    Enforces the 'Trinity of Trust' (Govern -> Verify -> Prove) during tool execution.
    """
    
    def __init__(self, orchestrator: SovereignAgent, config: Config = None):
        self.orchestrator = orchestrator
        self.config = config or Config.default()
        self.max_iterations = self.config.max_iterations
        self.client = httpx.AsyncClient(timeout=240.0)

    async def chat(self, user_input: str, state: AgentState) -> str:
        """
        Main entry point for the agentic reasoning loop.
        
        Args:
            user_input: The user prompt.
            state: Persistent state for the current session.
            
        Returns:
            The final answer or a security halt message.
        """
        # 1. System Prompt
        system_prompt = self._get_system_prompt()
        
        # 2. Execution Loop (ReAct)
        history = f"User: {user_input}\n"
        final_answer = ""
        
        try:
            for i in range(self.max_iterations):
                prompt = f"{system_prompt}\n{history}"
                
                # Call LLM
                response = await self._call_llm(prompt)
                logger.info(f"Loop {i+1} LLM Response: {response}")
                
                # Parse Thought and Action
                thought, action_match = self._parse_response(response)
                
                if not action_match:
                    # Look for Final Answer
                    final_match = re.search(r"Final Answer:\s*(.*)", response, re.DOTALL | re.IGNORECASE)
                    if final_match:
                        final_answer = final_match.group(1).strip()
                        break
                    else:
                        # If no tool call and no final answer, treat whole response as answer
                        final_answer = response.strip()
                        break
                
                tool_name = action_match.group(1)
                try:
                    tool_args = json.loads(action_match.group(2))
                except json.JSONDecodeError:
                    observation = "Error: Invalid JSON in tool arguments."
                    history += f"{response}\nObservation: {observation}\n"
                    continue

                # 3. Secure Tool Execution via Orchestrator
                try:
                    # In a real system, 'context' would come from a retrieval step
                    retrieved_context = state.metadata.get("context", "")
                    
                    # Contextual Idempotency: hash the history to allow re-execution if conversation moves
                    history_hash = hashlib.sha256(history.encode()).hexdigest()
                    
                    observation = await self.orchestrator.execute_tool(
                        tool_name, 
                        tool_args, 
                        state, 
                        retrieved_context,
                        context_version=history_hash
                    )
                except VerifyFailSignal as vfs:
                    # Verification failed - halt and inform the user out-of-band
                    logger.warning(f"Verification failure: {vfs}")
                    return f"SECURITY_HALT: Tool execution failed verification gate. [Ref: {vfs.signed_failure_hash[:12]}]"
                except SecurityHalt as sh:
                    # Governance or Idempotency denial
                    logger.warning(f"Security halt: {sh}")
                    return f"SECURITY_DENIAL: {str(sh)}"
                except Exception as e:
                    # General execution error
                    logger.error(f"Execution error: {e}")
                    observation = f"Error: Tool execution failed: {str(e)}"
                
                history += f"{response}\nObservation: {observation}\n"
                
            else:
                final_answer = "Error: Maximum reasoning iterations reached without final answer."

        except Exception as e:
            logger.exception("Fatal error in reasoning loop")
            final_answer = f"Error: An unexpected error occurred: {str(e)}"
            
        return final_answer

    def _get_system_prompt(self) -> str:
        return """You are 'sovereign_ai_agent', a secure AI assistant.
You follow a strict ReAct protocol to solve tasks.

Format:
Thought: Reasoning about what to do next.
Action: tool_name({"arg1": "val1"})
Observation: Output from the tool.
... (repeat if needed)
Final Answer: Your final response to the user.

Available Tools:
- read_file({"path": str})
- write_file({"path": str, "content": str})
- list_directory({"path": str})

Rules:
1. Always use 'Thought' before an 'Action'.
2. Tool arguments MUST be valid JSON.
3. Be concise and precise.
"""

    def _parse_response(self, response: str) -> Tuple[Optional[str], Optional[re.Match]]:
        thought_match = re.search(r"Thought:\s*(.*?)(?=Action:|Final Answer:|$)", response, re.DOTALL | re.IGNORECASE)
        thought = thought_match.group(1).strip() if thought_match else None
        
        action_match = re.search(r"Action:\s*(\w+)\((.*)\)", response, re.DOTALL | re.IGNORECASE)
        return thought, action_match

    async def _call_llm(self, prompt: str) -> str:
        """Call the local Ollama instance."""
        try:
            res = await self.client.post(
                f"{self.config.ollama_endpoint}/api/generate",
                json={
                    "model": self.config.default_model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"num_predict": 1024, "temperature": 0.1}
                }
            )
            res.raise_for_status()
            return res.json().get("response", "").strip()
        except Exception as e:
            logger.error(f"LLM Connection Error: {e}")
            raise RuntimeError(f"Could not connect to Ollama: {e}")

    async def close(self):
        await self.client.aclose()
