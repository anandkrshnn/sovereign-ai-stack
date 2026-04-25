import time
import uuid
import json
from typing import List, Dict, Any, Optional, Union, AsyncGenerator, Tuple

# Import Sovereign Components (Unified Monorepo)
from ..rag.main import AsyncLocalRAG as LocalRAG
from ..rag.schemas import RAGResponse
from ..verify.evaluator import SovereignEvaluator
from ..common.audit import SovereignAuditLogger, Principal
from ..common.identity import IdentityHub

try:
    from ..agent.core_loop import AgentCore as LocalAgent
except ImportError:
    LocalAgent = None

from opentelemetry import trace
from .schemas import ChatCompletionRequest, ChatCompletionResponse, ChatCompletionResponseChoice, ChatMessage, Usage, BackendType, BackendConfig
from .cache import SovereignSemanticCache

import httpx
import asyncio
import itertools
import os
import tiktoken
from .metrics import metrics

tracer = trace.get_tracer(__name__)

class SovereignOrchestrator:
    """
    The 'Brain' of local-bridge v1.0.0. 
    Manages physical tenant isolation and resource pooling.
    Supports Tiered Failover and High Availability.
    """

    def __init__(
        self, 
        base_dir: str = "data",
        default_model: str = "qwen2.5:7b", 
        backend_cluster: Optional[str] = None,
        max_rag_pool: int = 10,
        vector_dsn: Optional[str] = None
    ):
        self.base_dir = base_dir
        self.default_model = default_model
        self.max_rag_pool = max_rag_pool
        self.vector_dsn = vector_dsn or os.getenv("PGVECTOR_URL")
        self._http_client: Optional[httpx.AsyncClient] = None
        self._semaphore = asyncio.Semaphore(100)
        
        # Tenant Registry (Resource Pooling)
        self._tenant_resources: Dict[str, Dict[str, Any]] = {}
        self._rag_lru: List[str] = [] # List of tenant_ids sorted by usage
        
        # Parse Backend Cluster (v0.4.0)
        self.backends = self._parse_cluster(backend_cluster)
        self._round_robin_iter = {} # Priority Tier -> Iterator
        
        # Internal Verification Judge
        self.evaluator = SovereignEvaluator()
        
        # Background Tasks
        self._health_task = None
        self._maintenance_task = None

    def _get_tenant_resources(self, tenant_id: str, principal: str = "anonymous") -> Dict[str, Any]:
        """Lazy-load and pool per-tenant silos (v1.3.0)."""
        if tenant_id not in self._tenant_resources:
            # 1. Scoped Audit (Unified Forensic Chain)
            audit = SovereignAuditLogger(base_dir=self.base_dir, tenant_id=tenant_id)
            
            # 2. Scoped Semantic Cache
            cache = SovereignSemanticCache(base_dir=self.base_dir, tenant_id=tenant_id)
            
            self._tenant_resources[tenant_id] = {
                "audit": audit,
                "cache": cache,
                "rag": {}, # Map principal -> AsyncLocalRAG
                "last_used": time.time()
            }
            
        res = self._tenant_resources[tenant_id]
        res["last_used"] = time.time()
        
        # Update LRU
        if tenant_id in self._rag_lru:
            self._rag_lru.remove(tenant_id)
        self._rag_lru.append(tenant_id)
        
        return res

    async def _get_rag_instance(self, tenant_id: str, principal: str) -> Optional[Any]:
        """Get or initialize a pooled RAG instance with LRU protection (v1.0.0-GA)."""
        if not LocalRAG: return None
        
        res = self._get_tenant_resources(tenant_id, principal)
        pool = res["rag"]
        
        if principal not in pool:
            # ENFORCE LRU if global pool size exceeds limit
            await self._manage_rag_pool(tenant_id)
            
            db_path = os.path.join(self.base_dir, tenant_id, "retrieval.db")
            policy_path = os.path.join(self.base_dir, tenant_id, "policies", f"{principal}.yaml")
            
            # Initialize AsyncLocalRAG with GA attributes
            pool[principal] = LocalRAG(
                db_path=db_path,
                policy_path=policy_path,
                principal=principal,
                tenant_id=tenant_id,
                # roles/classifications can be injected here from JWT/Headers in a later pass
                vector_dsn=self.vector_dsn,
                use_reranker=True
            )
            metrics.sov_rag_pool_size.inc()
            
        return pool[principal]

    async def _manage_rag_pool(self, new_tenant_id: str):
        """Enforce LRU eviction if pool exceeds max_rag_pool."""
        # The new_tenant_id is already in _rag_lru at this point.
        # We only evict if we are strictly over the limit.
        while len(self._rag_lru) > self.max_rag_pool:
            # Pop the oldest tenant that IS NOT the current one
            idx = 0
            while idx < len(self._rag_lru) and self._rag_lru[idx] == new_tenant_id:
                idx += 1
            
            if idx < len(self._rag_lru):
                oldest_tenant = self._rag_lru.pop(idx)
                await self._evict_tenant(oldest_tenant, reason="lru")
            else:
                # Should not happen unless max_rag_pool < 1
                break

    async def _evict_tenant(self, tenant_id: str, reason: str = "ttl"):
        """Safely close and remove a tenant's pooled RAG instances."""
        if tenant_id in self._tenant_resources:
            res = self._tenant_resources[tenant_id]
            pool = res["rag"]
            for principal, rag in pool.items():
                if hasattr(rag, "close"):
                    await rag.close()
                metrics.sov_rag_pool_size.dec()
            
            pool.clear()
            metrics.sov_rag_pool_evictions_total.labels(reason=reason).inc()
            logger.info(f"🛡️  Evicted tenant RAG pool: {tenant_id} ({reason})")

    def _parse_cluster(self, cluster_str: Optional[str]) -> List[BackendConfig]:
        if not cluster_str:
            # Default to Ollama fallback
            return [BackendConfig(url="http://localhost:11434", type=BackendType.OLLAMA, priority=2)]
        
        backends = []
        for entry in cluster_str.split(","):
            try:
                # Format: Type:URL:Priority
                parts = entry.strip().split("|") # Using | for clarity in envs
                if len(parts) == 3:
                    b_type, b_url, b_prio = parts
                    backends.append(BackendConfig(url=b_url, type=BackendType(b_type), priority=int(b_prio)))
            except Exception as e:
                print(f"Error parsing backend entry {entry}: {e}")
        
        return sorted(backends, key=lambda x: x.priority)

    async def get_client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=120.0, limits=httpx.Limits(max_keepalive_connections=20, max_connections=100))
        return self._http_client

    async def start_health_checks(self):
        if self._health_task is None:
            self._health_task = asyncio.create_task(self._health_check_loop())
            
    async def start_cache_maintenance(self):
        if self._maintenance_task is None:
            self._maintenance_task = asyncio.create_task(self._cache_maintenance_loop())

    async def _health_check_loop(self):
        while True:
            client = await self.get_client()
            for b in self.backends:
                try:
                    check_url = f"{b.url}/api/tags" if b.type == BackendType.OLLAMA else f"{b.url}/v1/models"
                    res = await client.get(check_url, timeout=5.0)
                    b.is_healthy = res.status_code == 200
                except:
                    b.is_healthy = False
            await asyncio.sleep(30)
            
    async def _cache_maintenance_loop(self):
        while True:
            try:
                now = time.time()
                # 1. Global Cache Eviction
                # 2. RAG Pool TTL Eviction (15m idle)
                for tid in list(self._tenant_resources.keys()):
                    res = self._tenant_resources[tid]
                    res["cache"].evict_expired()
                    
                    if now - res.get("last_used", 0) > 900: # 15 minutes
                        await self._evict_tenant(tid, reason="ttl")
                        if tid in self._rag_lru: self._rag_lru.remove(tid)
                        
            except Exception as e:
                print(f"Maintenance Error: {e}")
            await asyncio.sleep(60) # Run every minute for tighter TTL

    async def _get_best_backend(self) -> BackendConfig:
        """Priority-based round robin."""
        # Find highest priority tier with at least one healthy backend
        healthy_by_prio = {}
        for b in self.backends:
            if b.is_healthy:
                healthy_by_prio.setdefault(b.priority, []).append(b)
        
        if not healthy_by_prio:
            # Absolute fallback: return the first backend and hope for the best
            return self.backends[0]
        
        best_prio = min(healthy_by_prio.keys())
        tier = healthy_by_prio[best_prio]
        
        if best_prio not in self._round_robin_iter:
            self._round_robin_iter[best_prio] = itertools.cycle(range(len(tier)))
            
        idx = next(self._round_robin_iter[best_prio]) % len(tier)
        return tier[idx]

    async def close(self):
        if self._health_task:
            self._health_task.cancel()
        if self._maintenance_task:
            self._maintenance_task.cancel()
        if self._http_client:
            await self._http_client.aclose()
        self._http_client = None
        # Close all pooled caches and RAG instances
        for res in self._tenant_resources.values():
            res["cache"].close()
            pool = res.get("rag", {})
            for rag in pool.values():
                if hasattr(rag, "close"):
                    await rag.close()

    async def complete(self, request: ChatCompletionRequest, tenant_id: str) -> Union[ChatCompletionResponse, AsyncGenerator[str, None]]:
        """
        Execute the sovereign orchestration loop with physical tenant isolation and metrics (v1.0.0).
        """
        # Identity Resolution (v1.0.0-GA Hardening)
        principal_obj = IdentityHub.resolve_mock(request.sovereign_principal or "anonymous", tenant_id=tenant_id)
        principal = principal_obj.id
        labels = metrics.get_labels(tenant_id, principal)
        
        # 1. TRACK CONCURRENCY
        metrics.sov_active_requests.labels(tenant_id=labels["tenant_id"]).inc()
        
        try:
            with tracer.start_as_current_span("sov_orchestration_loop") as span:
                start_time = time.time()
                last_message = request.messages[-1].content
                request_id = f"sov-{uuid.uuid4()}"
                
                # FETCH SCOPED RESOURCES (v1.0.0)
                res = self._get_tenant_resources(tenant_id)
                audit = res["audit"]
                cache = res["cache"]
                
                span.set_attribute("sov.tenant_id", tenant_id)
                span.set_attribute("sov.request_id", request_id)
                span.set_attribute("sov.principal", principal)
                
                # 0. SEMANTIC CACHE LOOKUP
                is_agent_query = any(keyword in last_message.lower() for keyword in ["write", "file", "save", "run"])
                
                if request.use_cache and not is_agent_query:
                    with tracer.start_as_current_span("sov_semantic_cache_lookup") as cspan:
                        cached = cache.lookup(last_message, principal)
                        if cached:
                            resp_text, model_name = cached
                            cspan.set_attribute("sov.cache_hit", True)
                            audit.log(request_id=request_id, principal=principal, outcome="cache_hit")
                            
                            # RECORD CACHE HIT
                            metrics.sov_cache_hits_total.labels(tenant_id=labels["tenant_id"]).inc()
                            metrics.sov_requests_total.labels(status="200", **labels).inc()
                            metrics.sov_request_duration_seconds.labels(tenant_id=labels["tenant_id"]).observe(time.time() - start_time)
                            
                            # Metering for Cache Hit (Estimated prompt tokens)
                            self._record_tokens(tenant_id, self.default_model, last_message, resp_text, 0, 0)
                            
                            return self._create_response(request, resp_text, request_id, principal, "cached", None, start_time, True)
                        cspan.set_attribute("sov.cache_hit", False)
                
                # 1. KNOWLEDGE RETRIEVAL (local-rag)
                use_reranker = request.use_reranker if request.use_reranker is not None else True
                results = []
                rag_event_id = None
                rag_reason = "disabled"
                context_text = ""
                
                if LocalRAG:
                    with tracer.start_as_current_span("sov_rag_retrieval") as rspan:
                        try:
                            # 1. Fetch Pooled Async Instance
                            rag = await self._get_rag_instance(tenant_id, principal)
                            
                            # 2. Async Call
                            rag_resp = await rag.ask(last_message, top_k=5)
                            
                            if isinstance(rag_resp, RAGResponse):
                                results = rag_resp.sources
                                context_text = rag_resp.answer if not rag_resp.answer.startswith("[") else ""
                                rag_reason = "authorized" if results else "denied/no-results"
                                rag_event_id = f"rag-{uuid.uuid4()}" 
                                
                                # Trace Attributes
                                rspan.set_attribute("sov.rag_results", len(results))
                                rspan.set_attribute("sov.rag_model", rag_resp.model_name)
                                
                                # Metric: Internal RAG Cache Hit
                                if "cached" in rag_resp.model_name:
                                    metrics.sov_rag_cache_hits_total.labels(tenant_id=labels["tenant_id"]).inc()
                                
                                # Metric: Policy Denied
                                if not results:
                                    metrics.sov_policy_denies_total.labels(**labels).inc()
                                    
                        except Exception as e:
                            context_text = f"Warning: RAG Retrieval Error: {e}"
                            rspan.record_exception(e)
            
                # 2. AUDIT LOGGING (Pre-Generation)
                audit.log("completion_started", principal_obj, {"query": last_message}, correlation_id=request_id)

            # 3. EXECUTION OR GENERATION
            async with self._semaphore:
                if LocalAgent and is_agent_query:
                    # Agent execution logic... (remaining from v1.0.0)
                    with tracer.start_as_current_span("sov_agent_execution") as aspan:
                        try:
                            loop = asyncio.get_event_loop()
                            resp, trace_id = await loop.run_in_executor(None, self._sync_agent_call, last_message, context_text, principal_obj)
                            audit.log("agent_executed", principal_obj, {"trace_id": trace_id}, correlation_id=request_id)
                            
                            metrics.sov_requests_total.labels(status="200", **labels).inc()
                            metrics.sov_request_duration_seconds.labels(tenant_id=labels["tenant_id"]).observe(time.time() - start_time)
                            
                            return self._create_response(request, str(resp), request_id, principal, rag_reason, trace_id, start_time)
                        except Exception as e:
                            metrics.sov_requests_total.labels(status="500", **labels).inc()
                            return self._create_response(request, f"Error: Agent Failure: {e}", request_id, principal, rag_reason, None, start_time)

                else:
                    if request.stream:
                        return self._stream_complete(request, context_text, request_id, principal, rag_reason, start_time, tenant_id)
                    else:
                        with tracer.start_as_current_span("sov_llm_generation_atomic") as lspan:
                            response_text = await self._call_llm_atomic(last_message, context_text, tenant_id)
                            
                            # 🛡️ SOVEREIGN VERIFICATION (The Airlock)
                            if context_text and self.evaluator:
                                with tracer.start_as_current_span("sov_verification_gate") as vspan:
                                    eval_res = self.evaluator.evaluate(last_message, context_text, response_text)
                                    vspan.set_attribute("sov.grounding_score", eval_res["grounding_score"])
                                    
                                    if not eval_res["passed"]:
                                        response_text = "[Sovereign Access Denied] The generated answer failed grounding verification and was redacted for safety."
                                        audit.log("verification_failed", principal_obj, {"query": last_message, "score": eval_res["grounding_score"]}, correlation_id=request_id)
                                    else:
                                        audit.log("verification_passed", principal_obj, {"query": last_message, "score": eval_res["grounding_score"]}, correlation_id=request_id)

                            if request.use_cache and not is_agent_query:
                                cache.store(last_message, response_text, self.default_model, principal)
                            
                            metrics.sov_requests_total.labels(status="200", **labels).inc()
                            metrics.sov_request_duration_seconds.labels(tenant_id=labels["tenant_id"]).observe(time.time() - start_time)
                            
                            return self._create_response(request, response_text, request_id, principal, rag_reason, None, start_time)
        finally:
            metrics.sov_active_requests.labels(tenant_id=labels["tenant_id"]).dec()

    # _sync_rag_call removed in v1.3.0 in favor of async pooling

    def _sync_agent_call(self, query: str, context: str, principal: Principal) -> Tuple[Any, str]:
        """Bridge to local-agent."""
        if not LocalAgent: return "Agent not available", ""
        agent = LocalAgent()
        resp = agent.chat(query, principal=principal)
        trace_id = getattr(agent, "current_trace", None)
        return resp, trace_id.trace_id if trace_id else ""

    async def _stream_complete(self, request, context, request_id, principal, rag_reason, start_time, tenant_id):
        """Streaming Generator supporting tiered failover, multi-tenant caching/metrics/metering."""
        labels = metrics.get_labels(tenant_id, principal)
        
        with tracer.start_as_current_span("sov_llm_generation_streaming") as span:
            last_message = request.messages[-1].content
            prompt = f"[SystemContext]: {context}\n\nUser: {last_message}" if context else last_message
            client = await self.get_client()
            full_response = []
            
            res = self._get_tenant_resources(tenant_id)
            cache = res["cache"]

            # Dynamic Backend Selection
            backend = await self._get_best_backend()
            span.set_attribute("sov.backend_url", backend.url)
            span.set_attribute("sov.backend_type", backend.type)

            target_url = f"{backend.url}/api/generate" if backend.type == BackendType.OLLAMA else f"{backend.url}/v1/chat/completions"
            payload = {
                "model": self.default_model, "prompt": prompt, "stream": True
            } if backend.type == BackendType.OLLAMA else {
                "model": self.default_model, "messages": [{"role": "user", "content": prompt}], "stream": True
            }

            reported_prompt_tokens = 0
            reported_completion_tokens = 0
            
            try:
                async with client.stream("POST", target_url, json=payload) as res:
                    res.raise_for_status()
                    async for line in res.aiter_lines():
                        if line:
                            chunk_text = ""
                            if backend.type == BackendType.OLLAMA:
                                body = json.loads(line)
                                chunk_text = body.get("response", "")
                                is_done = body.get("done", False)
                                if is_done:
                                    reported_prompt_tokens = body.get("prompt_eval_count", 0)
                                    reported_completion_tokens = body.get("eval_count", 0)
                            else:
                                if line.startswith("data: "):
                                    data_str = line.replace("data: ", "")
                                    if data_str == "[DONE]": break
                                    body = json.loads(data_str)
                                    chunk_text = body["choices"][0]["delta"].get("content", "")
                                    is_done = body["choices"][0].get("finish_reason") is not None
                                    # Streaming OpenAI usage is often in the final chunk (if requested)
                                    if "usage" in body:
                                        reported_prompt_tokens = body["usage"].get("prompt_tokens", 0)
                                        reported_completion_tokens = body["usage"].get("completion_tokens", 0)
                            
                            full_response.append(chunk_text)
                            chunk = {
                                "id": request_id, "object": "chat.completion.chunk", "created": int(time.time()), "model": self.default_model,
                                "choices": [{"index": 0, "delta": {"content": chunk_text}, "finish_reason": "length" if is_done else None}]
                            }
                            yield f"data: {json.dumps(chunk)}\n\n"
                            
                    final_text = "".join(full_response)
                    if request.use_cache:
                        cache.store(last_message, final_text, self.default_model, principal)
                        
                    # METRICS: Success
                    metrics.sov_requests_total.labels(status="200", **labels).inc()
                    metrics.sov_request_duration_seconds.labels(tenant_id=labels["tenant_id"]).observe(time.time() - start_time)
                    
                    # TOKEN METERING
                    self._record_tokens(labels["tenant_id"], self.default_model, prompt, final_text, reported_prompt_tokens, reported_completion_tokens)
                    
                    yield "data: [DONE]\n\n"
            except Exception as e:
                span.record_exception(e)
                metrics.sov_requests_total.labels(status="500", **labels).inc()
                yield f"data: {json.dumps({'error': f'Backend Failure ({backend.url}): {e}'})}\n\n"
                yield "data: [DONE]\n\n"

    async def _call_llm_atomic(self, message: str, context: str, tenant_id: str) -> str:
        prompt = f"[SystemContext]: {context}\n\nUser: {message}" if context else message
        client = await self.get_client()
        backend = await self._get_best_backend()
        
        target_url = f"{backend.url}/api/generate" if backend.type == BackendType.OLLAMA else f"{backend.url}/v1/chat/completions"
        payload = {"model": self.default_model, "prompt": prompt, "stream": False} if backend.type == BackendType.OLLAMA else {"model": self.default_model, "messages": [{"role": "user", "content": prompt}], "stream": False}
        
        try:
            res = await client.post(target_url, json=payload)
            res.raise_for_status()
            data = res.json()
            
            p_tokens = 0
            c_tokens = 0
            
            if backend.type == BackendType.OLLAMA:
                text = data.get("response", "").strip()
                p_tokens = data.get("prompt_eval_count", 0)
                c_tokens = data.get("eval_count", 0)
            else:
                text = data["choices"][0]["message"]["content"].strip()
                if "usage" in data:
                    p_tokens = data["usage"].get("prompt_tokens", 0)
                    c_tokens = data["usage"].get("completion_tokens", 0)
            
            # Record Tokens
            self._record_tokens(tenant_id, self.default_model, prompt, text, p_tokens, c_tokens)
            return text
        except Exception as e:
            return f"Error connecting to LLM backend ({backend.url}): {e}"

    def _record_tokens(self, tenant_id, model, prompt, completion, p_tokens, c_tokens):
        """Record token usage with high-precision tiktoken fallback (v1.0.0-GA)."""
        source_p = "reported" if p_tokens > 0 else "estimated"
        source_c = "reported" if c_tokens > 0 else "estimated"
        
        final_p = p_tokens
        final_c = c_tokens
        
        if final_p <= 0 or final_c <= 0:
            try:
                # Use tiktoken for high-precision estimation fallback
                encoding = tiktoken.encoding_for_model("gpt-3.5-turbo") # Baseline for cl100k_base
                if final_p <= 0:
                    final_p = len(encoding.encode(prompt))
                if final_c <= 0:
                    final_c = len(encoding.encode(completion))
            except:
                # Last resort heuristic
                if final_p <= 0: final_p = len(prompt) // 4
                if final_c <= 0: final_c = len(completion) // 4
        
        metrics.sov_tokens_total.labels(tenant_id=tenant_id, model=model, type="prompt", source=source_p).inc(final_p)
        metrics.sov_tokens_total.labels(tenant_id=tenant_id, model=model, type="completion", source=source_c).inc(final_c)

    def _create_response(self, request, text, request_id, principal, rag_reason, agent_trace_id, start_time, is_cached=False, audit_hash=None, chunks_cited=None, timing_meta=None):
        """
        Create a GA-standard response with conditional debug metadata (v1.0.0-GA).
        """
        latency = time.time() - start_time
        
        # Standard Sovereign Meta
        sovereign_meta = {
            "principal": principal,
            "rag_status": rag_reason,
            "audit_hash": audit_hash,
            "chunks_cited": chunks_cited,
            "latency_sec": latency,
            "gaip_compliant": True,
            "cache_hit": is_cached
        }
        
        if agent_trace_id:
            sovereign_meta["agent_trace_id"] = agent_trace_id
            
        # 🛡️ Governance Tax (Display only in debug mode)
        # Check for debug header/flag in request or ENV
        is_debug = getattr(request, "debug", False) or os.getenv("SOVEREIGN_DEBUG") == "1"
        
        if is_debug and timing_meta:
            sovereign_meta["governance_tax_ms"] = timing_meta.get("policy_eval_ms", 0) + timing_meta.get("audit_ms", 0)
            sovereign_meta["timing_breakdown"] = timing_meta
        
        return ChatCompletionResponse(
            id=request_id,
            created=int(time.time()),
            model=request.model,
            choices=[ChatCompletionResponseChoice(index=0, message=ChatMessage(role="assistant", content=text))],
            sovereign_meta=sovereign_meta
        )
