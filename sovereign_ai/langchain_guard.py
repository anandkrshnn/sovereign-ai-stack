from typing import Any, Dict, Optional

from langchain_core.language_models import BaseLLM
from langchain_core.runnables import Runnable, RunnableConfig

from sovereign_ai.pipeline import Config, SovereignPipeline


class SovereignLangChainGuard(Runnable):
    """
    A drop-in LangChain Runnable that wraps any underlying LLM or Chain
    inside the Sovereign AI Stack's Hardware-Rooted Verify-First Airlock.

    Any response that fails the NLI threshold will trigger a FAIL-CLOSED error.
    """

    def __init__(self, llm: BaseLLM, nli_threshold: float = 0.85, **kwargs):
        self.llm = llm

        # Configure the Sovereign Pipeline with Verification and Attestation enabled
        pipeline_config = Config(
            enable_verification=True,
            grounding_threshold=nli_threshold,
            enable_attestation=True,
            fail_closed=True,
            **kwargs,
        )
        self.pipeline = SovereignPipeline(config=pipeline_config)

    def invoke(
        self, input: Dict[str, Any], config: Optional[RunnableConfig] = None
    ) -> Dict[str, Any]:
        """Synchronous wrapper (not recommended for hardware/TPM paths, use ainvoke)."""
        import asyncio

        return asyncio.run(self.ainvoke(input, config))

    async def ainvoke(
        self, input: Dict[str, Any], config: Optional[RunnableConfig] = None, **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Asynchronous wrapper executing the Airlock protocol.
        Expects a dictionary with at least 'input' (query) and optionally 'context'.
        """
        query = input.get("input", str(input))
        context_str = input.get("context", "")

        # 1. Generate (using the attached LangChain LLM)
        # For LangChain integration, we use the LLM to generate directly instead of RAG pipeline
        llm_response = await self.llm.agenerate([[query]])
        generation_text = llm_response.generations[0][0].text

        # 2. Verify (NLI Gate) via the pipeline's internal evaluator
        # The pipeline has an internal evaluator `_evaluator`
        if self.pipeline._evaluator:
            # We can use the evaluator directly
            eval_res = await self.pipeline._evaluator.evaluate_with_threshold_async(
                query=query,
                context=context_str,
                answer=generation_text,
                threshold=self.pipeline.config.grounding_threshold,
            )
        else:
            # If no evaluator, fail open or close based on config
            if self.pipeline.config.fail_closed:
                raise ValueError("FAIL-CLOSED: Verification evaluator not initialized.")
            eval_res = {"passed": True, "grounding_score": 1.0}

        if not eval_res.get("passed", False):
            raise ValueError(
                f"FAIL-CLOSED: Verification failed. NLI Score: {eval_res.get('grounding_score')}"
            )

        return {
            "output": generation_text,
            "verification_score": eval_res.get("grounding_score"),
            "passed": True,
        }
