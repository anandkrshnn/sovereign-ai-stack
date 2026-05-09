from dataclasses import dataclass, field
from typing import List, Optional, Union, Dict, Any, AsyncGenerator
from .rag.main import AsyncLocalRAG, LocalRAG
from .rag.schemas import RAGResponse, Document

@dataclass
class Config:
    """Normalized configuration for the Sovereign AI Stack v1.1.0a2."""
    db_path: str = "sovereign.db"
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
    
    # [Policy Integrity]
    trusted_policy_key: Optional[str] = None
    strict_policy: bool = False
    
    # [Hardware Attestation]
    enable_attestation: bool = False
    
    # [Remote Attestation Enforcement]
    remote_verifier_url: Optional[str] = None
    require_remote_attestation: bool = False

class SovereignPipeline:
    """
    Sovereign AI Stack Pipeline Facade (v1.1.0a2).
    
    A stable public interface that orchestrates:
    1. Retrieval (sovereign-ai rag)
    2. Governance (sovereign-ai rag.policy)
    3. Verification (local-verify)
    """
    def __init__(self, config: Config):
        self.config = config
        # [Phase 3] Instantiate anchor via factory for cross-platform hardware trust
        from .common.hardware_trust import get_secure_anchor
        self.anchor = get_secure_anchor(config.tenant_id)

        # Mandatory Remote Attestation Gate (v0.1.0a5)
        if config.require_remote_attestation:
            import asyncio
            # We need a bridge for sync init
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If we're in a loop, we can't block. 
                    # In production, this should be called via an async factory.
                    import nest_asyncio
                    nest_asyncio.apply()
                    loop.run_until_complete(self._perform_remote_attestation())
                else:
                    loop.run_until_complete(self._perform_remote_attestation())
            except RuntimeError:
                asyncio.run(self._perform_remote_attestation())

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
            cache_dir=config.cache_dir,
            trusted_policy_key=config.trusted_policy_key,
            strict_policy=config.strict_policy,
            anchor=self.anchor,
            attest=config.enable_attestation
        )
        self._evaluator = None
        if config.enable_verification:
            try:
                from .verify.evaluator import SovereignEvaluator
                self._evaluator = SovereignEvaluator()
            except ImportError:
                print("Warning: local-verify components not found. Verification disabled.")

    async def _perform_remote_attestation(self):
        """
        Hardened Gate: Sends a hardware quote to the Remote Verifier.
        Halts pipeline if verification fails.
        """
        if not self.config.remote_verifier_url:
            from .common.schemas import SecurityHalt
            raise SecurityHalt("remote_verifier_url required when require_remote_attestation is True")

        import httpx
        import uuid
        from .common.schemas import SecurityHalt
        
        nonce = str(uuid.uuid4())
        quote = self.anchor.generate_quote(nonce=nonce, pcrs=[0, 11])
        
        payload = {
            "tenant_id": self.config.tenant_id,
            "nonce": nonce,
            "evidence": quote.model_dump()
        }
        
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self.config.remote_verifier_url}/verify/v1/attest",
                    json=payload,
                    timeout=10.0
                )
                
                if resp.status_code != 200:
                    raise SecurityHalt(f"Remote Attestation Rejected: {resp.text}")
                
                result = resp.json()
                if not result.get("success"):
                    raise SecurityHalt(f"Remote Attestation Failed: {result.get('message')}")
                
                print(f"DEBUG: Remote Attestation Verified by {self.config.remote_verifier_url}")
                
        except httpx.RequestError as e:
            if self.config.fail_closed:
                raise SecurityHalt(f"Verifier Unreachable: {e}")
            else:
                print(f"Warning: Verifier unreachable, but fail_closed=False. Proceeding with caution.")

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

    @staticmethod
    def from_text(text: str, tenant_id: str = "default", principal: str = "anonymous") -> "SovereignPipeline":
        """Convenience method for one-off document analysis."""
        import asyncio
        config = Config(tenant_id=tenant_id, principal=principal, enable_verification=True)
        pipeline = SovereignPipeline(config)
        
        doc = Document(
            doc_id="init-doc",
            source="memory",
            content=text,
            tenant_id=tenant_id
        )
        
        # We need a sync-to-async bridge for initialization if called from sync code
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            # This is tricky if already in a loop. We'll assume the user uses the async ingest for real work.
            # For from_text, we'll try to run it.
            pass 
        else:
            loop.run_until_complete(pipeline.ingest([doc]))
            
        return pipeline

    def ask_sync(self, query: str, intent: str = "general", top_k: int = 5) -> RAGResponse:
        """Synchronous wrapper for ask()."""
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        if loop.is_running():
            # If we're already in a loop, we can't use run_until_complete easily.
            # But for a simple script, this is fine.
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(self.ask(query, intent, top_k))
        else:
            return loop.run_until_complete(self.ask(query, intent, top_k))

    def __repr__(self):
        return f"<SovereignPipeline tenant={self.config.tenant_id} principal={self.config.principal}>"
