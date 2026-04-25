import os
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
from typing import Dict, Set

# Cardinality Guardrails (cncf best practices)
MAX_TENANTS = 100
MAX_PRINCIPALS_PER_TENANT = 50

class SovereignMetrics:
    def __init__(self):
        self.registry = CollectorRegistry()
        
        # 1. Request Counters
        self.sov_requests_total = Counter(
            "sov_requests_total", 
            "Total AI gateway requests", 
            ["tenant_id", "principal", "status"],
            registry=self.registry
        )
        
        # 2. Policy Denies (GAIP-2030 Invariant)
        self.sov_policy_denies_total = Counter(
            "sov_policy_denies_total", 
            "Requests denied by local-rag/local-agent policies", 
            ["tenant_id"], # Dropped principal to prevent cardinality bloat
            registry=self.registry
        )
        
        # 3. Semantic Cache Hits
        self.sov_cache_hits_total = Counter(
            "sov_cache_hits_total", 
            "Semantic cache hits (local disk)", 
            ["tenant_id"],
            registry=self.registry
        )
        
        # 4. Token Metering (v1.0.0 Phase 3)
        self.sov_tokens_total = Counter(
            "sov_tokens_total",
            "Total tokens consumed per tenant/model",
            ["tenant_id", "model", "type", "source"], # type=prompt|completion, source=reported|estimated
            registry=self.registry
        )
        
        # 5. Latency Histograms
        self.sov_request_duration_seconds = Histogram(
            "sov_request_duration_seconds", 
            "Request latency across the gateway", 
            ["tenant_id"],
            buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, float("inf")),
            registry=self.registry
        )
        
        # 6. Concurrency Gauge (For HA Scaling)
        self.sov_active_requests = Gauge(
            "sov_active_requests", 
            "Current active requests per tenant", 
            ["tenant_id"],
            registry=self.registry
        )

        # 7. RAG Pool Metrics (v1.3.0 Integration)
        self.sov_rag_pool_size = Gauge(
            "sov_rag_pool_size",
            "Number of active AsyncLocalRAG instances in memory",
            registry=self.registry
        )
        
        self.sov_rag_pool_evictions_total = Counter(
            "sov_rag_pool_evictions_total",
            "Total RAG instances evicted from pool (TTL or LRU)",
            ["reason"], # reason=ttl|lru
            registry=self.registry
        )
        
        self.sov_rag_cache_hits_total = Counter(
            "sov_rag_cache_hits_total",
            "Internal RAG-specific semantic cache hits",
            ["tenant_id"],
            registry=self.registry
        )

        # Cardinality Tracking Sets
        self._tracked_tenants: Set[str] = set()
        self._tracked_principals: Dict[str, Set[str]] = {}

    def is_valid_cardinality(self, tenant_id: str, principal: str = "anonymous") -> bool:
        """Enforce cardinality guardrails before recording metrics."""
        self._tracked_tenants.add(tenant_id)
        if len(self._tracked_tenants) > MAX_TENANTS:
            # Fallback to 'other' if too many tenants to protect Prometheus
            return False 
            
        if tenant_id not in self._tracked_principals:
            self._tracked_principals[tenant_id] = set()
            
        self._tracked_principals[tenant_id].add(principal)
        if len(self._tracked_principals[tenant_id]) > MAX_PRINCIPALS_PER_TENANT:
            return False
            
        return True

    def get_labels(self, tenant_id: str, principal: str = "anonymous") -> Dict[str, str]:
        """Get safe label set based on cardinality constraints."""
        if not self.is_valid_cardinality(tenant_id, principal):
            return {"tenant_id": "overflow", "principal": "overflow"}
        return {"tenant_id": tenant_id, "principal": principal}

# Global singleton
metrics = SovereignMetrics()
