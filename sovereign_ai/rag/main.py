from typing import Union, Generator, Optional, List, AsyncGenerator
import asyncio
from .governed import GovernedRetriever, AsyncGovernedRetriever
from .retriever import AsyncFTS5Retriever
from .generator import QwenGenerator
from .cache import SemanticCache
from .schemas import RAGResponse, SearchResult
from .prompts import DEFAULT_SYSTEM_PROMPT, RAG_USER_PROMPT

class LocalRAG:
    """
    Sovereign AI RAG Orchestrator.
    
    v0.4.0: Supports Data-at-Rest encryption via SQLCipher.
    """
    
    def __init__(
        self, 
        db_path: Optional[str] = None,
        policy_path: Optional[str] = None,
        principal: str = "anonymous",
        model_name: Optional[str] = None,
        password: Optional[str] = None,
        use_reranker: bool = False,
        reranker_model: str = "BAAI/bge-reranker-base"
    ):
        self.governed = policy_path is not None
        self.use_reranker = use_reranker
        
        if self.governed:
            self.retriever = GovernedRetriever(
                db_path=db_path, 
                policy_path=policy_path,
                principal=principal,
                password=password,
                use_reranker=use_reranker,
                reranker_model=reranker_model
            )
        else:
            # Legacy/Ungoverned Mode
            from .retriever import FTS5Retriever
            self.retriever = FTS5Retriever(db_path, password=password)
            
        # Ensure we don't pass None as model_name to avoid overriding QwenGenerator's default
        if model_name:
            self.generator = QwenGenerator(model_name=model_name)
        else:
            self.generator = QwenGenerator()
    
    def ask(self, query: str, top_k: int = 5, stream: bool = False) -> Union[RAGResponse, Generator[str, None, None]]:
        """
        Ask a question using the RAG pipeline. 
        In governed mode, retrieval passes through the Sovereign Airlock.
        """
        if self.governed:
            # Policy-mediated retrieval
            # When reranking is enabled, we fetch more candidates (100) and rerank to top_k
            results, decision = self.retriever.search(
                query, 
                top_k=100 if self.use_reranker else 20, 
                rerank_top_k=top_k
            )
            
            # Fail-closed: if policy denied everything, we don't even talk to the LLM
            if decision.action == "deny" and not results:
                refusal = f"[Sovereign Access Denied] {decision.reason}"
                if stream:
                    def gen(): yield refusal
                    return gen()
                return RAGResponse(answer=refusal, sources=[], model_name=self.generator.model_name)
        else:
            # Standard retrieval
            results = self.retriever.search(query, top_k=top_k)
        
        if not results:
            refusal = "[Insufficient Local Context] The local database does not have enough information to answer this query."
            if stream:
                def gen(): yield refusal
                return gen()
            return RAGResponse(answer=refusal, sources=[], model_name=self.generator.model_name)
            
        # Context construction
        context_text = self._format_context(results)
        
        # Generation
        messages = [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": RAG_USER_PROMPT.format(context=context_text, query=query)}
        ]
        
        if stream:
            return self.generator.stream_generate(messages)
        
        answer = self.generator.generate(messages)
        return RAGResponse(answer=answer, sources=results, model_name=self.generator.model_name)

    def _format_context(self, results: List[SearchResult]) -> str:
        """Format retrieved chunks into a context string with citations."""
        context_parts = []
        for i, res in enumerate(results, 1):
            context_parts.append(f"[{i}] source: {res.doc_id}\n{res.text}")
        return "\n\n".join(context_parts)

    def close(self):
        """Close database and logging connections."""
        self.retriever.close()

class AsyncLocalRAG:
    """
    Asynchronous Sovereign AI RAG Orchestrator.
    Optimized for high-concurrency production environments.
    """
    def __init__(
        self, 
        db_path: Optional[str] = None,
        policy_path: Optional[str] = None,
        principal: str = "anonymous",
        tenant_id: str = "default",
        roles: List[str] = None,
        classifications: List[str] = None,
        model_name: Optional[str] = None,
        password: Optional[str] = None,
        use_reranker: bool = False,
        reranker_model: str = "BAAI/bge-reranker-base",
        vector_dsn: Optional[str] = None,
        use_cache: bool = True,
        cache_dir: str = ".cache"
    ):
        self.governed = (policy_path is not None) or (tenant_id != "default")
        self.use_reranker = use_reranker
        self.tenant_id = tenant_id
        
        # 🏗️ Sovereign Airlock: Always use governed mode if tenanting is active
        if self.governed:
            self.retriever = AsyncGovernedRetriever(
                db_path=db_path, 
                policy_path=policy_path,
                principal=principal,
                tenant_id=tenant_id,
                roles=roles,
                classifications=classifications,
                password=password,
                use_reranker=use_reranker,
                reranker_model=reranker_model,
                vector_dsn=vector_dsn
            )
        else:
            self.retriever = AsyncFTS5Retriever(db_path, password=password)
            
        self.generator = QwenGenerator(model_name=model_name) if model_name else QwenGenerator()
        self.cache = SemanticCache(cache_dir=cache_dir) if use_cache else None

    async def ask(self, query: str, intent: str = "general", top_k: int = 5, stream: bool = False) -> Union[RAGResponse, AsyncGenerator[str, None]]:
        """
        Asynchronously ask a question with Semantic Caching and ABAC enforcement.
        """
        # 1. Semantic Cache Check (Siloed by Tenant)
        if self.cache and not stream:
            cached_res = await self.cache.get(query, tenant_id=self.tenant_id)
            if cached_res:
                return cached_res

        # 2 & 3: Retrieval & Policy Enforcement
        if self.governed:
            results, decision = await self.retriever.search(
                query, 
                intent=intent, 
                top_k=top_k
            )
            
            # 🛡️ Sovereign Hard Refusal (Fail-Closed)
            if decision.action == "deny":
                refusal = f"[Sovereign Access Denied] {decision.reason}"
                return RAGResponse(answer=refusal, sources=[], model_name=self.generator.model_name)
        else:
            results = await self.retriever.search(query, top_k=top_k)
        
        if not results:
            refusal = "[Insufficient Local Context] No relevant context found."
            if stream:
                async def gen(): yield refusal
                return gen()
            return RAGResponse(answer=refusal, sources=[], model_name=self.generator.model_name)
            
        context_text = self._format_context(results)
        messages = [
            {"role": "system", "content": DEFAULT_SYSTEM_PROMPT},
            {"role": "user", "content": RAG_USER_PROMPT.format(context=context_text, query=query)}
        ]
        
        if stream:
            # We wrap the sync generator in an async context for consistency
            async def async_stream_wrapper():
                for chunk in self.generator.stream_generate(messages):
                    yield chunk
            return async_stream_wrapper()
        
        # Generation is CPU/GPU bound, offload to thread to keep loop alive
        answer = await asyncio.to_thread(self.generator.generate, messages)
        
        # 4. Egress Secret Scanning (Fail-Closed)
        from .utils import contains_secret
        if contains_secret(answer):
            logger.error("Secret detected in generated answer! Redacting response.")
            answer = "[Sovereign Privacy Guardrail] The generated response was blocked due to potential credential leakage."
            results = [] # Strip sources if response was blocked
            
        response = RAGResponse(answer=answer, sources=results, model_name=self.generator.model_name)
        
        # 5. Cache Update
        if self.cache and not stream:
            await self.cache.set(query, response, tenant_id=self.tenant_id)
            
        return response

    def _format_context(self, results: List[SearchResult]) -> str:
        context_parts = []
        for i, res in enumerate(results, 1):
            context_parts.append(f"[{i}] source: {res.doc_id}\n{res.text}")
        return "\n\n".join(context_parts)

    async def close(self):
        await self.retriever.close()
