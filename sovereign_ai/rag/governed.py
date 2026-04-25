import hashlib
import uuid
import asyncio
from typing import List, Tuple, Optional
from datetime import datetime

from .retriever import FTS5Retriever, AsyncFTS5Retriever
from .policy import PolicyEngine
from .audit import AuditLogger
from .schemas import SearchResult, PolicyDecision, AuditRecord
from .reranker import BGEReranker
from .vector_store import PgVectorStore

from .policy import PolicyEngine, Principal, AccessRequest

class GovernedRetriever:
    """
    The Sovereign Airlock: Wraps FTS5Retriever with Policy Enforcement and Auditing.
    
    v1.0.0-GA: Supports Attribute-Based Access Control (ABAC).
    """
    
    def __init__(
        self, 
        db_path: str, 
        policy_path: str,
        principal: str = "anonymous",
        tenant_id: str = "default",
        roles: List[str] = None,
        classifications: List[str] = None,
        password: Optional[str] = None,
        use_reranker: bool = False,
        reranker_model: str = "BAAI/bge-reranker-base"
    ):
        self.retriever = FTS5Retriever(db_path, password=password)
        self.policy_engine = PolicyEngine(policy_path)
        self.audit_logger = AuditLogger()
        self.principal = Principal(
            id=principal,
            tenant_id=tenant_id,
            roles=roles or ["user"],
            classifications=classifications or ["public"]
        )
        self.policy_version = self.policy_engine.version
        self.reranker = BGEReranker(model_name=reranker_model) if use_reranker else None
        
    def search(self, query: str, intent: str = "general", top_k: int = 100, rerank_top_k: int = 5) -> Tuple[List[SearchResult], PolicyDecision]:
        """Execute a governed hybrid search with ABAC enforcement."""
        # 0. Construct Access Request
        request = AccessRequest(principal=self.principal, intent=intent, query=query)
        
        # 1. Retrieve Candidate Chunks
        candidates = self.retriever.search(query, top_k=top_k)
        
        # 2. Enforce Policy (ABAC Airlock)
        decision = self.policy_engine.evaluate_request(request, candidates)
        allowed_results = [r for r in candidates if r.chunk_id in decision.allowed_chunks]
        
        # 3. Hybrid Reranking (Cross-Encoder Precision)
        if self.reranker and allowed_results:
            results_to_return = self.reranker.rerank(query, allowed_results, top_k=rerank_top_k)
        else:
            results_to_return = allowed_results[:rerank_top_k]
            
        # 4. Audit Log
        audit_record = AuditRecord(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            principal=self.principal.id,
            query_hash=self._hash(query),
            query_preview=query[:100] + "..." if len(query) > 100 else query,
            decision=decision,
            candidate_count=len(candidates),
            allowed_count=len(results_to_return),
            denied_count=len(decision.denied_chunks),
            allowed_doc_ids=list(set([r.doc_id for r in results_to_return])),
            denied_doc_ids=list(set([r.doc_id for r in candidates if r.chunk_id in decision.denied_chunks]))
        )
        self.audit_logger.log(audit_record)
        return results_to_return, decision

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def close(self):
        self.retriever.close()
        self.audit_logger.close()

class AsyncGovernedRetriever:
    """Asynchronous Sovereign Airlock with ABAC support (v1.0.0-GA)."""
    def __init__(
        self, 
        db_path: str, 
        policy_path: str,
        principal: str = "anonymous",
        tenant_id: str = "default",
        roles: List[str] = None,
        classifications: List[str] = None,
        password: Optional[str] = None,
        use_reranker: bool = False,
        reranker_model: str = "BAAI/bge-reranker-base",
        vector_dsn: Optional[str] = None,
        vector_uri: Optional[str] = ".cache/lancedb"
    ):
        self.retriever = AsyncFTS5Retriever(db_path, password=password)
        self.policy_engine = PolicyEngine(policy_path)
        self.audit_logger = AuditLogger()
        self.principal = Principal(
            id=principal,
            tenant_id=tenant_id,
            roles=roles or ["user"],
            classifications=classifications or ["public"]
        )
        self.policy_version = self.policy_engine.version
        self.reranker = BGEReranker(model_name=reranker_model) if use_reranker else None
        
        # 🏗️ Hybrid Vector Choice: LanceDB (Local) or Postgres (Remote)
        from .vector_store import PgVectorStore, LanceVectorStore
        if vector_dsn:
            self.vector_store = PgVectorStore(dsn=vector_dsn)
        else:
            self.vector_store = LanceVectorStore(uri=vector_uri)

    async def search(self, query: str, intent: str = "general", top_k: int = 100, rerank_top_k: int = 5) -> Tuple[List[SearchResult], PolicyDecision]:
        """Execute an asynchronous hybrid governed search with ABAC enforcement."""
        # 0. Construct Access Request
        request = AccessRequest(principal=self.principal, intent=intent, query=query)
        
        # 1 & 2. Hybrid Retrieval (Parallel Fetch)
        tasks = [self.retriever.search(query, top_k=top_k)]
        if self.vector_store:
            tasks.append(self.vector_store.search(query, top_k=top_k))
        
        retrieval_results = await asyncio.gather(*tasks)
        
        # Merge results (Diversity Priority)
        seen_chunks = set()
        candidates = []
        for result_set in retrieval_results:
            for res in result_set:
                if res.chunk_id not in seen_chunks:
                    candidates.append(res)
                    seen_chunks.add(res.chunk_id)
        
        # 3. Policy Filter (ABAC Airlock)
        decision = self.policy_engine.evaluate_request(request, candidates)
        allowed_results = [r for r in candidates if r.chunk_id in decision.allowed_chunks]
        
        # 4. Rerank (Authorized Only)
        if self.reranker and allowed_results:
            results_to_return = await asyncio.to_thread(
                self.reranker.rerank, query, allowed_results, rerank_top_k
            )
        else:
            results_to_return = allowed_results[:rerank_top_k]
            
        # 5. Audit Log
        audit_record = AuditRecord(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            principal=self.principal.id,
            query_hash=self._hash(query),
            query_preview=query[:100] + "..." if len(query) > 100 else query,
            decision=decision,
            candidate_count=len(candidates),
            allowed_count=len(results_to_return),
            denied_count=len(decision.denied_chunks),
            allowed_doc_ids=list(set([r.doc_id for r in results_to_return])),
            denied_doc_ids=list(set([r.doc_id for r in candidates if r.chunk_id in decision.denied_chunks]))
        )
        await asyncio.to_thread(self.audit_logger.log, audit_record)
        return results_to_return, decision

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    async def close(self):
        await self.retriever.close()
        self.audit_logger.close()
