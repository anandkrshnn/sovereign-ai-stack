"""
Sovereign AI Stack - Local RAG with Cryptographic Verification
"""

__version__ = "1.0.0"

# Core exports
try:
    from .rag.main import LocalRAG
except ImportError:
    LocalRAG = None

try:
    from .verify.evaluator import SovereignEvaluator as LocalVerify
    from .verify.evaluator import SovereignEvaluator as GroundingJudge
except ImportError:
    LocalVerify = None
    GroundingJudge = None

from .pipeline import SovereignPipeline

# Optional imports (require extra dependencies)
try:
    from .bridge.main import app as SovereignBridge
except ImportError:
    SovereignBridge = None

try:
    # Use the broker or main entry point for the agent
    from .agent.core_loop import AgentCore as SovereignAgent
except ImportError:
    SovereignAgent = None

__all__ = [
    "LocalRAG",
    "LocalVerify",
    "GroundingJudge",
    "SovereignPipeline",
    "SovereignBridge",
    "SovereignAgent",
]
