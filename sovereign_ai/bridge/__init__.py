# Sovereign Bridge — canonical home for all code previously in the `local-bridge` satellite repo
__version__ = "0.1.0-preview"

from .schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    BackendType,
    BackendConfig,
)

try:
    from .main import app
except ImportError:
    app = None

try:
    from .orchestrator import SovereignOrchestrator
except ImportError:
    SovereignOrchestrator = None

try:
    from .metrics import SovereignMetrics
    metrics = SovereignMetrics()
except ImportError:
    SovereignMetrics = None
    metrics = None

__all__ = [
    "__version__",
    "app",
    "SovereignOrchestrator",
    "ChatCompletionRequest",
    "ChatCompletionResponse",
    "ChatMessage",
    "BackendType",
    "BackendConfig",
    "SovereignMetrics",
    "metrics",
]
