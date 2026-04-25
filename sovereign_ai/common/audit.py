import json
import hashlib
import uuid
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field, asdict

@dataclass
class AuditRecord:
    """Unified audit record for forensic chaining."""
    event_id: str
    timestamp: float
    correlation_id: str
    event_type: str
    principal: Dict[str, Any]
    data: Dict[str, Any]
    prev_hash: str
    chain_hash: Optional[str] = None

@dataclass
class Principal:
    """Unified identity principal for the Sovereign AI Stack."""
    id: str
    tenant_id: str = "default"
    roles: List[str] = field(default_factory=lambda: ["user"])
    classifications: List[str] = field(default_factory=lambda: ["public"])
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

class AuditChainManager:
    """
    Cryptographic hash chain manager for tamper-evident auditing (v1.0.0-GA).
    """
    GENESIS_HASH = "genesis"

    @staticmethod
    def calculate_next_hash(prev_hash: str, entry: dict) -> str:
        # Remove any existing hash to ensure idempotency
        entry_copy = entry.copy()
        entry_copy.pop("chain_hash", None)
        
        # Canonicalization (Sorted keys, no whitespace)
        canonical = json.dumps(entry_copy, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(f"{prev_hash}{canonical}".encode()).hexdigest()

class SovereignAuditLogger:
    """
    The unified auditor for the Sovereign AI Stack.
    Supports physical tenant isolation and hash-chaining.
    """
    def __init__(self, base_dir: str, tenant_id: str):
        self.base_dir = Path(base_dir)
        self.tenant_id = tenant_id
        self.log_path = self.base_dir / tenant_id / "audit" / "sovereign_audit.jsonl"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._last_hash = None

    def log(self, event_type: str, principal: Principal, data: Dict[str, Any], correlation_id: Optional[str] = None):
        """Log an event to the tenant's chain."""
        if self._last_hash is None:
            self._last_hash = self._get_last_hash()

        entry = {
            "timestamp": time.time(),
            "event_id": str(uuid.uuid4()),
            "correlation_id": correlation_id or str(uuid.uuid4()),
            "event_type": event_type,
            "principal": principal.to_dict(),
            "data": data,
            "prev_hash": self._last_hash
        }

        curr_hash = AuditChainManager.calculate_next_hash(self._last_hash, entry)
        entry["chain_hash"] = curr_hash
        
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
        
        self._last_hash = curr_hash
        return curr_hash

    def _get_last_hash(self) -> str:
        if not self.log_path.exists():
            return AuditChainManager.GENESIS_HASH
        
        try:
            with open(self.log_path, "rb") as f:
                f.seek(0, 2)
                if f.tell() == 0:
                    return AuditChainManager.GENESIS_HASH
                
                # Backward-seek to find the last line
                f.seek(max(-1024, -f.tell()), 2)
                lines = f.read().decode("utf-8", errors="ignore").splitlines()
                if not lines:
                    return AuditChainManager.GENESIS_HASH
                
                last_line = lines[-1].strip()
                if not last_line:
                    return AuditChainManager.GENESIS_HASH
                
                return json.loads(last_line).get("chain_hash", AuditChainManager.GENESIS_HASH)
        except Exception:
            return AuditChainManager.GENESIS_HASH

    def verify_integrity(self) -> bool:
        """Full chain validation."""
        if not self.log_path.exists():
            return True
            
        prev_hash = AuditChainManager.GENESIS_HASH
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line.strip())
                    expected_hash = AuditChainManager.calculate_next_hash(prev_hash, entry)
                    if entry.get("chain_hash") != expected_hash:
                        return False
                    prev_hash = expected_hash
            return True
        except Exception:
            return False
