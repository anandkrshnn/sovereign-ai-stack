from typing import Dict, Any
from .config import DEFAULT_DB_PATH

def compute_sovereign_score(config: Any, metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute a diagnostic 'Sovereign Score' (0-10) based on measurable attributes.
    
    This is a self-assessment tool and not a replacement for formal security audits.
    """
    weights = {
        "isolation": 3.0,    # Physical tenant silos
        "forensics": 2.5,    # Hash-chained audit
        "performance": 2.0,  # p50 latency benchmarks
        "compliance": 1.5,   # ABAC policy coverage
        "portability": 1.0,  # Offline/edge capability
    }
    
    # 1. Isolation Scan
    # Check if the DB is in a scoped tenant path and if encryption is active
    isolation_base = 10.0 if "silos" in str(config.getattr("db_path", "")).lower() else 5.0
    if config.getattr("encrypted", False):
        isolation_base = 10.0
    
    # 2. Forensics Scan
    forensics_base = 10.0 if config.getattr("audit_chain_enabled", True) else 0.0
    
    # 3. Performance Scan (p50_ms vs threshold)
    p50 = metrics.get("p50_cached_ms", 5.0)
    perf_score = max(0.0, 10.0 - (p50 - 5.0) * 0.5)
    
    # 4. Compliance Scan (Rule depth)
    rules_count = len(getattr(config, "policy_rules", []))
    compliance_score = min(10.0, rules_count * 2.5)
    
    # 5. Portability Scan
    portability_score = 10.0 # Default local-rag is highly portable
    
    scores = {
        "isolation": isolation_base,
        "forensics": forensics_base,
        "performance": perf_score,
        "compliance": compliance_score,
        "portability": portability_score,
    }
    
    weighted_total = sum(weights[k] * scores[k] for k in weights)
    final_score = round(weighted_total / sum(weights.values()), 1)
    
    return {
        "score": final_score,
        "components": scores,
        "recommendations": _get_recommendations(scores)
    }

def _get_recommendations(scores: Dict[str, float]) -> list[str]:
    recs = []
    if scores["isolation"] < 10:
        recs.append("Enable SQLCipher encryption and use per-tenant DB paths.")
    if scores["forensics"] < 10:
        recs.append("Enable AuditChainManager for tamper-evident logging.")
    if scores["compliance"] < 5:
        recs.append("Define standard ABAC policy rules in policy.yaml.")
    return recs

class ScoreConfig:
    """Mock config for score calculation if full RAG object isn't available."""
    def __init__(self, db_path: str, policy_rules: list = None, encrypted: bool = False):
        self.db_path = db_path
        self.policy_rules = policy_rules or []
        self.encrypted = encrypted
        self.audit_chain_enabled = True

    def getattr(self, name, default):
        return getattr(self, name, default)
