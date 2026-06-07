from dataclasses import dataclass, field
from typing import Dict, Optional, Any

@dataclass
class Config:
    """Normalized configuration for the Sovereign AI Stack verification pipeline."""
    tenant_id: str = "default"
    grounding_threshold: float = 0.85
    fail_closed: bool = True
    enable_attestation: bool = False
    
class SovereignPipeline:
    """
    Sovereign AI Stack Pipeline Facade (v0.2.0-alpha).
    A pure verification interface.
    """
    def __init__(self, config: Config):
        self.config = config
        from .common.hardware_trust import get_secure_anchor
        self.anchor = get_secure_anchor(config.tenant_id)
        
        self._evaluator = None
        try:
            from .verify.evaluator import SovereignEvaluator
            self._evaluator = SovereignEvaluator()
        except ImportError:
            pass

    async def initialize(self):
        """Initialize the pipeline and hardware anchor."""
        if self.config.enable_attestation:
            import uuid
            nonce = str(uuid.uuid4())
            self.anchor.generate_quote(nonce=nonce, pcrs=[0, 11])

    async def verify(self, query: str, context: str, answer: str) -> Dict[str, Any]:
        """
        Verify the generated answer against the context and query.
        Returns the verification result.
        """
        if not self._evaluator:
            return {"passed": False, "error": "Evaluator not found."}
            
        try:
            eval_res = await self._evaluator.evaluate_with_threshold_async(
                query, context, answer, threshold=self.config.grounding_threshold
            )
        except AttributeError:
            eval_res = await self._evaluator.evaluate_async(query, context, answer)
            
        if not eval_res.get("passed", False) and self.config.fail_closed:
            eval_res["safe_answer"] = "[Sovereign Access Denied] Answer failed grounding verification."
        else:
            eval_res["safe_answer"] = answer
            
        return eval_res

    def __repr__(self):
        return f"<SovereignPipeline tenant={self.config.tenant_id}>"
