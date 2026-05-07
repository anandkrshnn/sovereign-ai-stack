"""
sovereign_ai.rag
~~~~~~~~~~~~~~~~
Sovereign AI RAG Orchestrator — governed, encrypted, locally-sovereign retrieval.

Core API:
    LocalRAG          — Synchronous governed RAG pipeline (policy + FTS5 + Ollama)
    AsyncLocalRAG     — Async governed RAG with tenant isolation, ABAC, semantic cache
    RAGResponse       — Typed response container (answer, sources, model_name)
    SearchResult      — Single retrieved chunk with doc_id, text, score, classification

Advanced:
    GovernedRetriever       — Sync retriever with Sovereign Airlock policy enforcement
    AsyncGovernedRetriever  — Async retriever with tenant-scoped ABAC
    SemanticCache           — Tenant-siloed semantic similarity cache
    FTS5Retriever           — Legacy / ungoverned FTS5 retriever
    QwenGenerator           — Local Ollama-backed generator

Phase 1 consolidation note:
    This package is the canonical home for all RAG logic previously
    in the local-rag satellite repository (now deprecated).
    The monorepo version is ahead: it adds GovernedRetriever, AsyncLocalRAG,
    tenant isolation, SQLCipher encryption, and egress secret scanning.
    Do NOT sync backward to sovereign-ai rag; archive that repo instead.

Version: 0.4.0
"""

from .main import LocalRAG, AsyncLocalRAG
from .retriever import FTS5Retriever, AsyncFTS5Retriever
from .generator import QwenGenerator
from .governed import GovernedRetriever, AsyncGovernedRetriever
from .schemas import RAGResponse, SearchResult
from .cache import SemanticCache
from .policy import PolicyEngine
from ..common.audit import SovereignAuditLogger

__all__ = [
    # Primary interface
    "LocalRAG",
    "AsyncLocalRAG",
    # Types
    "RAGResponse",
    "SearchResult",
    # Governed retrieval
    "GovernedRetriever",
    "AsyncGovernedRetriever",
    # Supporting
    "FTS5Retriever",
    "AsyncFTS5Retriever",
    "QwenGenerator",
    "SemanticCache",
    "PolicyEngine",
    "SovereignAuditLogger",
]
