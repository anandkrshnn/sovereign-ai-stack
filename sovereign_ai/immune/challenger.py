import logging
from typing import Optional, Tuple, Dict, Any

from sovereign_ai.immune.events import KnowledgeEvent
from sovereign_ai.immune.brain import VerifiedBrain
from sovereign_ai.gates.nli_gate import NLIAdaptiveGate

logger = logging.getLogger(__name__)

class ChallengerAgent:
    """
    The T-cell Challenger Agent (Adaptive Immunity).
    Actively audits incoming knowledge proposals (antigens) by performing 
    rigorous, targeted pairwise consistency checks against existing verified facts.
    """
    def __init__(self, nli_gate: Optional[NLIAdaptiveGate] = None):
        self.nli_gate = nli_gate

    def challenge(self, event: KnowledgeEvent, brain: VerifiedBrain) -> Tuple[bool, Optional[str], Dict[str, Any]]:
        """
        Audits a proposed KnowledgeEvent against the VerifiedBrain's Layer 1.
        
        Returns:
        - is_challenged (bool): True if a contradiction is detected.
        - conflicting_knowledge (str | None): The specific fact that contradicts the antigen.
        - audit_metadata (dict): The probability details of the audit.
        """
        gate = self.nli_gate or brain.nli_gate
        logger.info("Challenger T-cell auditing proposed antigen: %s", event.event_id)

        # Retrieve related facts from Layer 1
        # In a full system, this uses Vector + BM25 keyword retrieval.
        # To ensure absolute logical rigor, we scan existing Layer 1 facts.
        target_knowledge = brain.layer_1_verified_layer
        
        if not target_knowledge:
            return False, None, {"reason": "Verified layer is empty, no target to challenge."}

        for existing_fact in target_knowledge:
            # Run high-fidelity pairwise sequence classification
            probs = gate.get_probabilities(premise=existing_fact, hypothesis=event.payload)
            contradiction_score = probs["contradiction"]

            if contradiction_score >= gate.contradiction_threshold:
                logger.warning(
                    "🔥 Contradiction detected by Challenger! Proposed: '%s' contradicts existing: '%s' (Score: %.3f)",
                    event.payload, existing_fact, contradiction_score
                )
                
                # Increment brain challenge counter
                brain.recent_challenges_count += 1
                
                # Inject the contradiction into the brain's audit list for dynamic autoimmune boost
                brain.recent_rejection_history.append(True)
                if len(brain.recent_rejection_history) > brain.evaluation_window_size:
                    brain.recent_rejection_history.pop(0)
                brain.apply_autoimmune_safeguard()
                
                # Quarantine the conflicting event if it is already accepted, or prevent insertion
                return True, existing_fact, {
                    "reason": "Pairwise contradiction detected",
                    "probabilities": probs,
                    "threshold_applied": gate.contradiction_threshold
                }

        logger.info("Challenger audit complete. No contradictions found in existing verified memory.")
        return False, None, {"reason": "No contradictions found."}
