import yaml
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

from .schemas import SearchResult, PolicyDecision

logger = logging.getLogger(__name__)

@dataclass
class Principal:
    """Identity and attributes of the requester for ABAC."""
    id: str
    tenant_id: str
    roles: List[str]
    classifications: List[str]
    metadata: Dict[str, Any] = None

@dataclass
class AccessRequest:
    """The context of a single retrieval attempt."""
    principal: Principal
    intent: str  # e.g., "treatment", "billing", "research"
    query: str

class PolicyEngine:
    """
    Sovereign ABAC Policy Engine for RAG authorization (v1.0.0-GA).
    
    Acts as the 'Sovereign Airlock', filtering chunks based on principal attributes.
    """
    
    def __init__(self, policy_path: Optional[str] = None):
        if policy_path:
            self.policy_path = Path(policy_path)
        else:
            self.policy_path = None
        self.policy = self._load_policy()
        self.version = self.policy.get("version", "1.0.0-GA")
    
    def _load_policy(self) -> Dict[str, Any]:
        """Load YAML policy or return default safe policy if missing."""
        if not self.policy_path or not self.policy_path.exists():
            logger.warning("Policy file not found. Using 'Deny-All' safety default.")
            return {"allow": [], "deny": [{"classification": "all"}], "limits": {"max_results": 0}}
            
        try:
            with open(self.policy_path, "r", encoding="utf-8") as f:
                policy = yaml.safe_load(f)
            return policy or {}
        except Exception as e:
            logger.error(f"Error loading policy: {e}")
            return {"allow": [], "deny": [{"classification": "all"}]}
    
    def evaluate_request(self, request: AccessRequest, results: List[SearchResult]) -> PolicyDecision:
        """Evaluate an AccessRequest against candidate search results using ABAC attributes."""
        from .utils import contains_secret
        
        allow_rules = self.policy.get("allow", [])
        deny_rules = self.policy.get("deny", [])
        limits = self.policy.get("limits", {})
        
        allowed_results = []
        denied_ids = []
        
        for res in results:
            # 1. SECRET SCAN (Global Guardrail)
            if contains_secret(res.text):
                logger.warning(f"Secret detected in chunk {res.chunk_id}. Forced denial.")
                denied_ids.append(res.chunk_id)
                continue

            chunk_metadata = res.metadata
            is_authorized = False
            
            # 1. DENY RULES (Override EVERYTHING)
            is_denied = False
            for rule in deny_rules:
                if self._match_rule(rule, request.principal, chunk_metadata, request.intent):
                    is_denied = True
                    break
            
            if is_denied:
                logger.debug(f"Chunk {res.chunk_id} explicitly DENIED by rule.")
                denied_ids.append(res.chunk_id)
                continue
                
            # 2. ALLOW RULES (Deny-by-Default)
            for rule in allow_rules:
                if self._match_rule(rule, request.principal, chunk_metadata, request.intent):
                    is_authorized = True
                    logger.debug(f"Chunk {res.chunk_id} AUTHORIZED by rule: {rule}")
                    break
                    
            if is_authorized:
                min_score = limits.get("min_score", 0.0)
                if res.score >= min_score:
                    allowed_results.append(res)
                else:
                    logger.debug(f"Chunk {res.chunk_id} filtered by score: {res.score} < {min_score}")
                    denied_ids.append(res.chunk_id)
            else:
                logger.debug(f"Chunk {res.chunk_id} NOT AUTHORIZED (No matching allow rule).")
                denied_ids.append(res.chunk_id)
        
        # 4. Limit results
        max_results = limits.get("max_results", len(allowed_results))
        final_allowed = allowed_results[:max_results]
        
        for dropped in allowed_results[max_results:]:
            denied_ids.append(dropped.chunk_id)
            
        action = "allow" if final_allowed else "deny"
        if len(final_allowed) < len(allowed_results):
            action = "limit"
            
        return PolicyDecision(
            action=action,
            reason=self._generate_reason(action, len(final_allowed), len(denied_ids)),
            allowed_chunks=[r.chunk_id for r in final_allowed],
            denied_chunks=denied_ids,
            limit_applied=max_results if action == "limit" else None
        )

    def _match_rule(self, rule: Dict[str, Any], principal: Principal, chunk_meta: Dict[str, Any], intent: str) -> bool:
        """Attribute-based matching logic (ABAC)."""
        # Support both singular and plural for better flexibility
        rule_intents = rule.get("intents") or rule.get("intent")
        if rule_intents and intent not in rule_intents:
            return False
            
        if "roles" in rule:
            if not any(role in principal.roles for role in rule["roles"]):
                return False
                
        if "classifications" in rule:
            chunk_class = chunk_meta.get("classification")
            if chunk_class not in rule["classifications"] and "all" not in rule["classifications"]:
                return False
                    
        # 🛡️ Mandatory Tenant Isolation (Implicitly enforced in every rule)
        rule_tenant = rule.get("tenant_id")
        if rule_tenant != "any":
            if principal.tenant_id != chunk_meta.get("tenant_id"):
                return False
                
        return True

    def _generate_reason(self, action: str, allowed_count: int, denied_count: int) -> str:
        if action == "deny" and allowed_count == 0:
            return f"Sovereign Deny: 0/{(allowed_count+denied_count)} chunks authorized. Access restricted by v{self.version} ABAC policy."
        return f"Sovereign {action.capitalize()}: {allowed_count} authorized, {denied_count} filtered."
