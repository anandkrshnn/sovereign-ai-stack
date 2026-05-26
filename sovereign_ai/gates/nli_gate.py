import logging
from typing import List, Dict, Any, Tuple
import torch
import torch.nn.functional as F
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from sovereign_ai.common.airlock import SovereignAirlock, AirlockResult

logger = logging.getLogger(__name__)

# DeBERTa-v3 NLI mapping: 0=contradiction, 1=entailment, 2=neutral
_LABELS = ["contradiction", "entailment", "neutral"]

class NLIAdaptiveGate(SovereignAirlock):
    """
    An advanced Natural Language Inference (NLI) gate featuring:
    - Entailment Mode (strict verification)
    - Consistency Mode (fail-closed contradiction prevention)
    - Dynamic thresholds (Autoimmune Safeguard)
    - Quarantine boundaries for high-uncertainty claims
    """
    def __init__(
        self, 
        model_name: str = "cross-encoder/nli-deberta-v3-base", 
        entailment_threshold: float = 0.85,
        contradiction_threshold: float = 0.60
    ):
        self.model_name = model_name
        self.entailment_threshold = entailment_threshold
        self.contradiction_threshold = contradiction_threshold
        self.tokenizer = None
        self.model = None
        self.device = "cpu"

    def _load_model(self) -> None:
        if self.model is None:
            logger.info("Initializing NLI Gate: %s", self.model_name)
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.model_name,
                torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
            )
            self.model.eval()
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.model = self.model.to(self.device)

    def set_thresholds(self, entailment: float, contradiction: float) -> None:
        """
        Dynamically adjusts the thresholds (e.g., during Autoimmune response).
        """
        self.entailment_threshold = entailment
        self.contradiction_threshold = contradiction
        logger.info("NLI thresholds dynamically updated. Entailment: %s, Contradiction: %s", entailment, contradiction)

    def get_probabilities(self, premise: str, hypothesis: str) -> Dict[str, float]:
        """
        Runs sequence classification over the premise and hypothesis and 
        returns the probability distribution across contradiction, entailment, and neutral.
        """
        self._load_model()
        
        inputs = self.tokenizer(
            [premise],
            [hypothesis],
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            logits = self.model(**inputs).logits

        probs = F.softmax(logits, dim=-1)[0].tolist()
        return {
            "contradiction": float(probs[0]),
            "entailment": float(probs[1]),
            "neutral": float(probs[2])
        }

    async def verify(self, claim: str, context: List[str]) -> AirlockResult:
        """
        Standard Airlock compliance check. Requires strict ENTAILMENT.
        """
        if not context:
            return AirlockResult(is_safe=False, score=0.0, reason="No context provided", metadata={})

        combined_context = " ".join(context)
        probs = self.get_probabilities(combined_context, claim)
        entailment = probs["entailment"]

        is_safe = entailment >= self.entailment_threshold
        reason = "Entailment Verified" if is_safe else f"Insufficient Entailment (Score: {entailment:.3f} < {self.entailment_threshold})"
        
        return AirlockResult(
            is_safe=is_safe,
            score=entailment,
            reason=reason,
            metadata={"probabilities": probs, "threshold": self.entailment_threshold, "mode": "strict_entailment"}
        )

    def verify_consistency(self, proposed_update: str, current_knowledge: List[str]) -> Tuple[str, Dict[str, float], str]:
        """
        Executes Innate Immunity logic. Checks if the proposed antigen is logically consistent 
        with existing knowledge.
        
        Decisions:
        - "ACCEPT": If entailment is high and contradiction is low.
        - "REJECT": If contradiction probability exceeds the contradiction_threshold (Fail-Closed).
        - "QUARANTINE": If the contradiction is low but entailment is also low (Neutral/Unverifiable state).
        """
        if not current_knowledge:
            # If the vault is empty, we must accept the initial anchoring event
            return "ACCEPT", {"contradiction": 0.0, "entailment": 1.0, "neutral": 0.0}, "Initial context insertion (Inherent trust)"

        combined_knowledge = " ".join(current_knowledge)
        probs = self.get_probabilities(combined_knowledge, proposed_update)
        
        contradiction = probs["contradiction"]
        entailment = probs["entailment"]

        # 1. Active contradiction detection (Innate Defense) -> Fail-closed
        if contradiction >= self.contradiction_threshold:
            return "REJECT", probs, f"Active Contradiction Detected (Contradiction: {contradiction:.3f} >= {self.contradiction_threshold})"
        
        # 2. Strong Entailment (Direct reinforcement) -> Direct acceptance
        if entailment >= self.entailment_threshold:
            return "ACCEPT", probs, f"Strong Logical Entailment (Entailment: {entailment:.3f} >= {self.entailment_threshold})"
        
        # 3. High Neutral/Unsure (Borderline / New Antigen) -> Quarantine Zone
        return "QUARANTINE", probs, f"Unverified / Neutral Information (Contradiction: {contradiction:.3f}, Entailment: {entailment:.3f})"
