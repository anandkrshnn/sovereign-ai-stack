from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any, AsyncGenerator
from .main import AsyncLocalRAG, LocalRAG
from .schemas import RAGResponse, Document

@dataclass
class Config:
    """Normalized configuration for the Sovereign AI Stack v1.0.0-GA."""
    db_path: Optional[str] = None
    policy_path: Optional[str] = None
    principal: str = "anonymous"
    tenant_id: str = "default"
    roles: List[str] = field(default_factory=list)
    classifications: List[str] = field(default_factory=list)
    model_name: Optional[str] = None
    password: Optional[str] = None
    use_reranker: bool = False
    reranker_model: str = "BAAI/bge-reranker-base"
    vector_dsn: Optional[str] = None
    use_cache: bool = True
    cache_dir: str = ".cache"
    fail_closed: bool = True  # GA principle: default to safety
    
    # [local-verify integration]
    enable_verification: bool = False
    grounding_threshold: float = 0.85
    faithfulness_threshold: float = 0.90

class RAGPipeline:
    """
    Sovereign RAG Pipeline Facade (v1.0.0-GA).
    
    A stable public interface that wraps the production AsyncLocalRAG engine.
    Ensures consistent configuration, audit wiring, and policy enforcement.
    """
    def __init__(self, config: Config):
        self.config = config
        self._engine = AsyncLocalRAG(
            db_path=config.db_path,
            policy_path=config.policy_path,
            principal=config.principal,
            tenant_id=config.tenant_id,
            roles=config.roles,
            classifications=config.classifications,
            model_name=config.model_name,
            password=config.password,
            use_reranker=config.use_reranker,
            reranker_model=config.reranker_model,
            vector_dsn=config.vector_dsn,
            use_cache=config.use_cache,
            cache_dir=config.cache_dir
        )
        self._evaluator = None
        if config.enable_verification:
            try:
                from local_verify import SovereignEvaluator
                self._evaluator = SovereignEvaluator()
            except ImportError:
                print("Warning: local-verify not found. Verification disabled.")

    async def ask(self, query: str, intent: str = "general", top_k: int = 5, stream: bool = False) -> Union[RAGResponse, AsyncGenerator[str, None]]:
        """
        Execute a governed RAG query via the underlying engine.
        """
        res = await self._engine.ask(query, intent=intent, top_k=top_k, stream=stream)
        
        # Post-generation Verification
        if self._evaluator and not stream:
            # Construct context string for grounding check
            if not res.sources:
                eval_res = {"grounding_score": 0.0, "faithfulness_score": 0.0, "overall_score": 0.0, "passed": False}
            else:
                context = "\n\n".join([s.text for s in res.sources])
                eval_res = self._evaluator.evaluate(query, context, res.answer)
            
            # Staple evaluation to result metadata
            res.metadata["verification"] = eval_res
            
            if not eval_res["passed"] and self.config.fail_closed:
                res.answer = "[Sovereign Access Denied] Answer failed grounding verification (hallucination risk)."
                res.sources = [] # Remove sources to prevent leaked misinformation
        
        return res

    async def ingest(self, docs: List[Document], chunk_size: int = 1000, chunk_overlap: int = 200):
        """
        Asynchronously ingest documents into the sovereign vault.
        """
        if hasattr(self._engine.retriever, "retriever"):
            # Governed mode
            await self._engine.retriever.retriever.ingest_batch(docs, chunk_size, chunk_overlap)
        else:
            # Ungoverned mode
            await self._engine.retriever.ingest_batch(docs, chunk_size, chunk_overlap)

    async def close(self):
        """Cleanly shutdown the engine and its resources."""
        await self._engine.close()

    def __repr__(self):
        return f"<RAGPipeline tenant={self.config.tenant_id} principal={self.config.principal}>"
