import yaml
import logging
import base64
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519, ec
from cryptography.hazmat.primitives import hashes

from .schemas import SearchResult, PolicyDecision

logger = logging.getLogger(__name__)

from ..common.audit import Principal

@dataclass
class AccessRequest:
    """The context of a single retrieval attempt."""
    principal: Principal
    intent: str  # e.g., "treatment", "billing", "research"
    query: str

class PolicyEngine:
    """
    Sovereign ABAC Policy Engine for RAG authorization (v1.1.0a2).
    
    Acts as the 'Sovereign Airlock', filtering chunks based on principal attributes.
    """
    
    def __init__(self, policy_path: Optional[str] = None, trusted_public_key: Optional[Union[bytes, str]] = None, strict_mode: bool = False):
        """
        Initialize the Policy Engine.
        
        Args:
            policy_path: Path to policy YAML.
            trusted_public_key: Raw bytes or B64 string of the public key allowed to sign policies.
            strict_mode: If True, rejection of unsigned or invalid policies is mandatory.
        """
        if policy_path:
            self.policy_path = Path(policy_path)
        else:
            self.policy_path = None
            
        self.trusted_public_key = self._parse_public_key(trusted_public_key)
        self.strict_mode = strict_mode
        self.policy = self._load_policy()
        self.version = self.policy.get("version", "1.1.0a2")

    def _parse_public_key(self, key_data: Optional[Union[bytes, str]]):
        if not key_data:
            return None
        if isinstance(key_data, str):
            try:
                return base64.b64decode(key_data)
            except:
                return key_data.encode()
        return key_data

    def verify_signature(self) -> bool:
        """Verify the policy file against its .sig counterpart."""
        if not self.policy_path or not self.trusted_public_key:
            return not self.strict_mode

        sig_path = self.policy_path.with_suffix(self.policy_path.suffix + ".sig")
        if not sig_path.exists():
            logger.error(f"Policy signature MISSING at {sig_path}")
            return False

        try:
            with open(self.policy_path, "rb") as f:
                content = f.read()
            with open(sig_path, "r", encoding="utf-8") as f:
                signature = base64.b64decode(f.read())

            # Verification logic based on key type
            # We assume Ed25519 (Software) or P-256 (TPM)
            if len(self.trusted_public_key) == 32: # Ed25519
                pub = ed25519.Ed25519PublicKey.from_public_bytes(self.trusted_public_key)
                pub.verify(signature, content)
            else: # Assume P-256
                from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
                pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), self.trusted_public_key)
                pub.verify(signature, content, ec.ECDSA(hashes.SHA256()))
                
            logger.info(f"Policy signature VERIFIED for {self.policy_path}")
            return True
        except Exception as e:
            logger.error(f"Policy signature VERIFICATION FAILED: {e}")
            return False
    
    def _load_policy(self) -> Dict[str, Any]:
        """Load YAML policy or return default safe policy if missing/invalid."""
        # 1. Existence Check
        if not self.policy_path or not self.policy_path.exists():
            logger.warning(f"Policy file NOT FOUND at {self.policy_path}. Using 'Deny-All' safety default.")
            return {"allow": [], "deny": [{"classification": "all"}], "limits": {"max_results": 0}}
            
        # 2. Integrity Check (Signed Policies)
        if self.trusted_public_key or self.strict_mode:
            if not self.verify_signature():
                logger.critical("FORCED POLICY DENIAL: Signature invalid or missing in strict mode.")
                return {"allow": [], "deny": [{"classification": "all"}], "limits": {"max_results": 0}}

        # 3. YAML Parse
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
            p_tenant = principal.tenant_id
            c_tenant = chunk_meta.get("tenant_id")
            if p_tenant != c_tenant:
                return False
        
        # 5. Generic Attribute Matching (e.g. "departments", "projects")
        # Any key not explicitly handled above is checked against chunk metadata
        for key, value in rule.items():
            if key in ["intents", "intent", "roles", "classifications", "tenant_id", "version"]:
                continue
            
            # Support plural/singular mismatch (e.g. rule has "departments", meta has "department")
            meta_key = key
            if key.endswith("s") and key[:-1] in chunk_meta:
                meta_key = key[:-1]
            elif key not in chunk_meta and key + "s" in chunk_meta:
                meta_key = key + "s"
                
            if meta_key in chunk_meta:
                chunk_val = chunk_meta[meta_key]
                if isinstance(value, list):
                    if chunk_val not in value:
                        return False
                elif chunk_val != value:
                    return False
            else:
                # If rule specifies an attribute that is MISSING from chunk, it cannot match
                return False
                
        return True

    def _generate_reason(self, action: str, allowed_count: int, denied_count: int) -> str:
        if action == "deny" and allowed_count == 0:
            return f"Sovereign Deny: 0/{(allowed_count+denied_count)} chunks authorized. Access restricted by v{self.version} ABAC policy."
        return f"Sovereign {action.capitalize()}: {allowed_count} authorized, {denied_count} filtered."
