"""
Sovereign AI Stack - Local RAG with Cryptographic Verification
"""

__version__ = "1.0.0"

# RAG Components
from .rag.main import LocalRAG, AsyncLocalRAG
from .rag.store import Store
from .rag.retriever import FTS5Retriever
from .rag.generator import QwenGenerator
from .rag.pipeline import SovereignPipeline, Config
from .rag.schemas import Document, SearchResult, AuditRecord, RAGResponse, PolicyDecision
from .rag.policy import PolicyEngine, Principal, AccessRequest
from .rag.audit import AuditLogger, KeyringProvider
from .rag.governed import GovernedRetriever, AsyncGovernedRetriever
from .rag.db_utils import get_db_status, encrypt_database, decrypt_database, rekey_database
from .rag.hub import app as hub_app
from .rag.utils import RecursiveCharacterTextSplitter, chunk_text, contains_secret
from .rag.reranker import BGEReranker

# Main Platform Facade
from .pipeline import SovereignPipeline, Config as SovereignConfig

# Bridge Gateway
try:
    from .bridge.main import app as SovereignBridge
except ImportError:
    SovereignBridge = None

# Forensic Agent
try:
    from .agent.core_loop import AgentCore as SovereignAgent
except ImportError:
    SovereignAgent = None

__all__ = [
    "LocalRAG",
    "AsyncLocalRAG",
    "Store",
    "FTS5Retriever",
    "QwenGenerator",
    "SovereignPipeline",
    "Config",
    "Document",
    "SearchResult",
    "AuditRecord",
    "RAGResponse",
    "PolicyDecision",
    "PolicyEngine",
    "Principal",
    "AccessRequest",
    "AuditLogger",
    "KeyringProvider",
    "GovernedRetriever",
    "AsyncGovernedRetriever",
    "get_db_status",
    "encrypt_database",
    "decrypt_database",
    "rekey_database",
    "hub_app",
    "RecursiveCharacterTextSplitter",
    "chunk_text",
    "contains_secret",
    "BGEReranker",
    "SovereignPipeline",
    "SovereignConfig",
    "SovereignBridge",
    "SovereignAgent",
]
