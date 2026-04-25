import os
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Config:
    sandbox_root: Path = Path.home() / "LocalAgentSandbox"
    default_model: str = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
    ollama_endpoint: str = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    audit_db: str = "lpb_audit.db"
    memory_db: str = "agent_memory.duckdb"
    max_iterations: int = 4
    
    # Milestone 4: Bridge Config
    bridge_secret: str = os.getenv("LOCALAGENT_BRIDGE_SECRET", "localagent-default-secret-change-me")
    bridge_enabled: bool = os.getenv("LOCALAGENT_BRIDGE_ENABLED", "True").lower() == "true"
    
    # Phase 2: Security Hardening
    secret_scanner_entropy_threshold: float = float(os.getenv("SECRET_SCANNER_ENTROPY_THRESHOLD", "4.5"))
    secret_scanner_fail_open: bool = os.getenv("SECRET_SCANNER_FAIL_OPEN", "False").lower() == "true"
    jitter_local_ms_range: tuple = (0.0, 0.02)
    jitter_bridge_ms_range: tuple = (0.05, 0.20)
    
    # Secret Scanner Hardening (v0.2.0-RELEASE)
    scanner_max_payload_kb: int = 100
    scanner_timeout_ms: int = 500
    scanner_fail_open_on_timeout: bool = False
    secret_scanner_fail_open: bool = False
    secret_scanner_entropy_threshold: float = float(os.getenv("SECRET_SCANNER_ENTROPY_THRESHOLD", "4.5"))

    @classmethod
    def default(cls):
        return cls()
