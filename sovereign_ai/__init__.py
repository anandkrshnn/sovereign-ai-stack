"""
Sovereign AI Stack - Local RAG with Cryptographic Verification
"""

__version__ = "0.1.0a5"

from .agent.forensics.audit_chain import AuditChainManager as SignedAuditChain
# --- Core Platform Facade ---
from .pipeline import Config, SovereignPipeline
# --- RAG & Retrieval ---
from .rag import AsyncLocalRAG, LocalRAG
from .rag.governed import GovernedRetriever as HybridRetriever
from .rag.schemas import AuditRecord, Document, RAGResponse, SearchResult
# --- Verification & Forensics ---
from .verify import SovereignEvaluator

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
