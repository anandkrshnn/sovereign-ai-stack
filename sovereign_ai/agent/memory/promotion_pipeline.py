from typing import Dict, List, Any
from datetime import datetime
import json
import uuid
from localagent.memory.lancedb_store import LanceDBStore

PROMOTION_PIPELINE_MAX_QUEUED = 500

class MemoryPromotionPipeline:
    """Extracts and promotes candidate memories from episodic logs."""
    
    def __init__(self, lancedb_store: LanceDBStore):
        self.lancedb_store = lancedb_store
        self.active_queue = 0
        self._lock = __import__("threading").Lock()

    def run_cycle(self, episode_id: str, content: str, trace_id: str = "NO_TRACE"):
        """Standard promotion cycle: Extract, Deduplicate, Persist."""
        with self._lock:
            if self.active_queue >= PROMOTION_PIPELINE_MAX_QUEUED:
                print(f"[Promotion] Queue flooded (> {PROMOTION_PIPELINE_MAX_QUEUED}). Evicting extraction to protect LPB.")
                return
            self.active_queue += 1
            
        try:
            candidates = self.extract_candidates({"episode_id": episode_id, "content_text": content, "trace_id": trace_id})
            
            for candidate in candidates:
                # Semantic deduplication: Check for highly similar items in memory_items
                is_duplicate = self._check_duplicate(candidate["body"])
                if not is_duplicate:
                    # Get vector embedding for the item
                    from localagent.memory import get_embedder
                    embedder = get_embedder()
                    vector = embedder.encode(candidate["body"]).tolist() if embedder else [0.0]*384
                    
                    # Persist to LanceDB
                    self.lancedb_store.promote_memory(candidate, vector)
                    print(f"[Promotion] New candidate saved: {candidate['body'][:40]}... ({candidate['sensitivity']})")
                else:
                    print(f"[Promotion] Ignored duplicate: {candidate['body'][:40]}...")
        finally:
            with self._lock:
                self.active_queue -= 1

    def extract_candidates(self, episode: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract candidate memory items based on H/M/L scale."""
        text = episode.get("content_text", "")
        if not text: return []
        
        candidates = []
        lower_text = text.lower()
        
        # 1. High Sensitivity (Secrets/Credentials)
        # Using simple patterns for demonstration; in production, use specialized NER or LLM
        if any(kw in lower_text for kw in ["password", "secret", "key", "token", "login"]):
            candidates.append({
                "body": text,
                "memory_type": "secret",
                "sensitivity": "High",
                "confidence": 0.95,
                "status": "candidate", # High always starts as candidate for review
                "source_episode_id": episode.get("episode_id"),
                "source_trace_id": episode.get("trace_id", "NO_TRACE"),
                "trust_score": 0.5, # Default trust requires UI elevation
                "metadata": {"reason": "Matches secret keyword"}
            })
            
        # 2. Medium Sensitivity (Project/Work Context)
        elif any(kw in lower_text for kw in ["project", "context", "plan", "build"]):
            candidates.append({
                "body": text,
                "memory_type": "project",
                "sensitivity": "Medium",
                "confidence": 0.8,
                "status": "approved", # Auto-approve Medium for now (per plan)
                "source_episode_id": episode.get("episode_id"),
                "source_trace_id": episode.get("trace_id", "NO_TRACE"),
                "trust_score": 0.8, # Auto-trust medium projects
                "metadata": {"reason": "Matches project keyword"}
            })
            
        # 3. Low Sensitivity (Preferences/Style)
        elif any(kw in lower_text for kw in ["prefer", "always", "style", "format"]):
            candidates.append({
                "body": text,
                "memory_type": "preference",
                "sensitivity": "Low",
                "confidence": 0.9,
                "status": "approved", # Auto-approve Low
                "source_episode_id": episode.get("episode_id"),
                "source_trace_id": episode.get("trace_id", "NO_TRACE"),
                "trust_score": 0.9,
                "metadata": {"reason": "Matches preference keyword"}
            })
            
        return candidates

    def _check_duplicate(self, text: str) -> bool:
        """Simple semantic check for duplicates in memory_items."""
        items = self.lancedb_store.get_memory_items()
        for item in items:
            # Coarse text overlap check; in production, use vector similarity threshold
            if text.lower() in item["body"].lower() or item["body"].lower() in text.lower():
                return True
        return False
