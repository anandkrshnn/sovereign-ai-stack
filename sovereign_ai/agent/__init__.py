__version__ = "0.2.0"

from .signing import sign_payload

try:
    from .core_loop import AgentCore
except ImportError:
    AgentCore = None

try:
    from .config import Config as AgentConfig
except ImportError:
    AgentConfig = None

__all__ = [
    "__version__",
    "sign_payload",
    "AgentCore",
    "AgentConfig",
]