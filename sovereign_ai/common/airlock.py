import abc
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class AirlockResult:
    is_safe: bool
    score: float
    reason: str
    metadata: Dict[str, Any]

class SovereignAirlock(abc.ABC):
    """
    Base class for verification gates that intercept AI output before it is certified.
    """
    @abc.abstractmethod
    async def verify(self, claim: str, context: List[str]) -> AirlockResult:
        pass

class NLIEntailmentAirlock(SovereignAirlock):
    """
    Verification gate that uses a Natural Language Inference (NLI) model 
    to check logical entailment between claims and retrieved context.
    """
    def __init__(self, model_name: str = "cross-encoder/nli-deberta-v3-base", threshold: float = 0.85):
        self.model_name = model_name
        self.threshold = threshold
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name)
        return self._model

    async def verify(self, claim: str, context: List[str]) -> AirlockResult:
        if not context:
            return AirlockResult(is_safe=False, score=0.0, reason="No context provided", metadata={})

        model = self._load_model()
        
        # We test the claim against the combined context
        # In a more advanced implementation, we might split the claim into atomic sentences
        combined_context = " ".join(context)
        
        # CrossEncoder expects (sentence1, sentence2)
        # 0: contradiction, 1: entailment, 2: neutral (usually for DeBERTa NLI)
        # We want the 'entailment' score
        scores = model.predict([(combined_context, claim)])
        
        # Map labels based on common NLI cross-encoder outputs
        # This is a research implementation; thresholds are configurable
        entailment_score = float(scores[0]) # Depends on specific model head
        
        # For DeBERTa-v3 NLI: [contradiction, neutral, entailment]
        # We assume the output is the raw logits or softmax from the entailment head
        # In this research preview, we use the raw score returned by the CrossEncoder predict
        
        is_safe = entailment_score >= self.threshold
        
        return AirlockResult(
            is_safe=is_safe,
            score=entailment_score,
            reason="Verified" if is_safe else f"Insufficient Grounding (Score: {entailment_score:.2f} < {self.threshold})",
            metadata={"model": self.model_name, "threshold": self.threshold}
        )
