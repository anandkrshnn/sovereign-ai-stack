"""
Sovereign AI Stack - Local RAG with Cryptographic Verification
"""

__version__ = "0.1.0a5"

# --- Core Platform Facade ---
from .pipeline import SovereignPipeline, Config

# --- RAG & Retrieval ---
from .rag import LocalRAG, AsyncLocalRAG
from .rag.governed import GovernedRetriever as HybridRetriever
from .rag.schemas import Document, SearchResult, RAGResponse, AuditRecord

# --- Verification & Forensics ---
from .verify import SovereignEvaluator
from .agent.forensics.audit_chain import AuditChainManager as SignedAuditChain

# --- Agentic Workflows ---
try:
    from .agent.core_loop import AgentCore as SovereignAgent
except ImportError:
    SovereignAgent = None

# --- Bridge Gateway ---
try:
    from .bridge.main import app as SovereignBridge
except ImportError:
    SovereignBridge = None

__all__ = [
    "SovereignPipeline",
    "Config",
    "LocalRAG",
    "AsyncLocalRAG",
    "HybridRetriever",
    "Document",
    "SearchResult",
    "RAGResponse",
    "AuditRecord",
    "SovereignEvaluator",
    "SignedAuditChain",
    "SovereignAgent",
    "SovereignBridge",
]
