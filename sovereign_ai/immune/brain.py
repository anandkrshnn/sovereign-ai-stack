import logging
import hashlib
from typing import List, Dict, Any, Optional

from sovereign_ai.immune.events import KnowledgeEvent
from sovereign_ai.gates.nli_gate import NLIAdaptiveGate

logger = logging.getLogger(__name__)

class VerifiedBrain:
    """
    The Verified Adaptive Company Brain (Immune System Brain).
    Coordinates the 3 memory layers, runs the self-evolving loop, and dynamically
    manages thresholds via the Autoimmune Safeguard.
    """
    def __init__(
        self,
        nli_gate: Optional[NLIAdaptiveGate] = None,
        base_entailment_threshold: float = 0.85,
        base_contradiction_threshold: float = 0.60
    ):
        self.nli_gate = nli_gate or NLIAdaptiveGate(
            entailment_threshold=base_entailment_threshold,
            contradiction_threshold=base_contradiction_threshold
        )
        
        self.base_entailment = base_entailment_threshold
        self.base_contradiction = base_contradiction_threshold

        # 3-Layer Memory Hierarchy
        self.layer_0_raw_vault: List[KnowledgeEvent] = []  # Immutable signed originals
        self.layer_1_verified_layer: List[str] = []         # NLI-approved knowledge base
        self.layer_2_wisdom_layer: List[str] = []           # Distilled principles / policies

        # Quarantine Zone
        self.quarantine_zone: Dict[str, Dict[str, Any]] = {}

        # Cryptographic Audit Chain
        self.merkle_leaves: List[str] = []
        self.current_merkle_root: str = "0" * 64

        # Adaptive Metrics
        self.recent_challenges_count = 0
        self.evaluation_window_size = 10
        self.recent_rejection_history: List[bool] = []  # Tracks last N updates (True if rejected/quarantined)

    def propose_update(self, event: KnowledgeEvent, public_key_hex: Optional[str] = None) -> Dict[str, Any]:
        """
        Receives an Antigen (proposed change), verifies signatures, runs innate immunity checks, 
        and updates the memory layers accordingly.
        """
        logger.info("Processing proposed knowledge update: %s", event.event_id)

        # 1. Cryptographic Signature Verification
        if public_key_hex:
            if not event.verify_signature(public_key_hex):
                logger.error("Cryptographic signature verification failed for event: %s", event.event_id)
                return {"status": "REJECT", "reason": "Invalid cryptographic signature", "event_id": event.event_id}

        # 2. Immutable Logging (Layer 0 Raw Vault addition)
        event.parent_hash = self.current_merkle_root
        self.layer_0_raw_vault.append(event)
        self.merkle_leaves.append(event.merkle_hash)
        self._recompute_merkle_root()

        # 3. Innate Immunity Check (Consistency check using NLI gate)
        decision, probs, reason = self.nli_gate.verify_consistency(
            proposed_update=event.payload,
            current_knowledge=self.layer_1_verified_layer
        )

        logger.info("Innate immunity verdict: %s (Reason: %s)", decision, reason)

        # Update metrics for Autoimmune Safeguard
        is_suspicious = decision in ["REJECT", "QUARANTINE"]
        self.recent_rejection_history.append(is_suspicious)
        if len(self.recent_rejection_history) > self.evaluation_window_size:
            self.recent_rejection_history.pop(0)

        # Apply Autoimmune Safeguard to dynamically scale security thresholds
        self.apply_autoimmune_safeguard()

        if decision == "ACCEPT":
            # Add to Layer 1 (Verified Layer)
            self.layer_1_verified_layer.append(event.payload)
            # Check for structural principles (Layer 2)
            if event.metadata.get("distilled_principle", False) or event.payload.startswith("PRINCIPLE:"):
                self.layer_2_wisdom_layer.append(event.payload)
            
            return {
                "status": "ACCEPT",
                "reason": reason,
                "event_id": event.event_id,
                "merkle_root": self.current_merkle_root,
                "probabilities": probs
            }

        elif decision == "REJECT":
            return {
                "status": "REJECT",
                "reason": reason,
                "event_id": event.event_id,
                "probabilities": probs
            }

        else:  # QUARANTINE
            self.quarantine_zone[event.event_id] = {
                "event": event,
                "reason": reason,
                "probabilities": probs,
                "resolved": False
            }
            return {
                "status": "QUARANTINE",
                "reason": reason,
                "event_id": event.event_id,
                "probabilities": probs
            }

    def resolve_quarantine(self, event_id: str, action: str) -> bool:
        """
        Manually or algorithmically overrides a quarantined event.
        Action must be "APPROVE" or "DISCARD".
        """
        if event_id not in self.quarantine_zone:
            return False

        item = self.quarantine_zone[event_id]
        if item["resolved"]:
            return False

        event = item["event"]
        if action == "APPROVE":
            logger.info("Manually approving quarantined event: %s", event_id)
            self.layer_1_verified_layer.append(event.payload)
            if event.metadata.get("distilled_principle", False) or event.payload.startswith("PRINCIPLE:"):
                self.layer_2_wisdom_layer.append(event.payload)
            item["resolved"] = True
            return True
        elif action == "DISCARD":
            logger.info("Discarding quarantined event: %s", event_id)
            item["resolved"] = True
            return True

        return False

    def apply_autoimmune_safeguard(self) -> None:
        """
        Dynamic Threshold Scaling. If the suspicion/rejection rate over the current
        window exceeds 40%, the system assumes a coordinate knowledge pollution attack
        and dynamically increases NLI strictness to protect core memory.
        """
        if not self.recent_rejection_history:
            return

        rejection_rate = sum(self.recent_rejection_history) / len(self.recent_rejection_history)
        
        if rejection_rate >= 0.40:
            # Scale up strictness: increase entailment requirements and lower contradiction tolerance
            boost_factor = (rejection_rate - 0.30) * 0.20  # Max boost ~0.14
            new_entailment = min(0.98, self.base_entailment + boost_factor)
            new_contradiction = max(0.40, self.base_contradiction - boost_factor)
            
            logger.warning(
                "🚨 Autoimmune Safeguard Triggered! Rejection rate: %.2f%%. Raising thresholds.", 
                rejection_rate * 100
            )
            self.nli_gate.set_thresholds(entailment=new_entailment, contradiction=new_contradiction)
        else:
            # Cool down to baseline security settings
            self.nli_gate.set_thresholds(entailment=self.base_entailment, contradiction=self.base_contradiction)

    def _recompute_merkle_root(self) -> None:
        """
        Recomputes the cryptographic Merkle root of all raw logging hashes.
        Uses a simple hash chain to represent the tree sequence recursively.
        """
        if not self.merkle_leaves:
            self.current_merkle_root = "0" * 64
            return

        current_hash = self.merkle_leaves[0]
        for leaf in self.merkle_leaves[1:]:
            combined = current_hash + leaf
            current_hash = hashlib.sha256(combined.encode('utf-8')).hexdigest()

        self.current_merkle_root = current_hash
        logger.info("New secure memory Merkle root: %s", self.current_merkle_root)
