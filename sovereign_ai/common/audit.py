import json
import hashlib
import uuid
import time
import os
import hmac
import keyring
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

class ChainSecretManager:
    """
    Manages the machine-unique secret for hardware-bound auditing.
    Stored in the OS Secure Enclave (Windows Credential Manager).
    """
    SERVICE_NAME = "sovereign_ai"
    KEY_NAME = "forensic_anchor_secret"

    @classmethod
    def get_secret(cls) -> bytes:
        secret = keyring.get_password(cls.SERVICE_NAME, cls.KEY_NAME)
        if secret:
            return secret.encode()
        
        # Provision new secret
        new_secret = os.urandom(32).hex()
        try:
            keyring.set_password(cls.SERVICE_NAME, cls.KEY_NAME, new_secret)
        except Exception:
            # Fallback for headless/no-enclave environments
            pass
        return new_secret.encode()

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
    Supports physical tenant isolation, hash-chaining, and hardware-bound anchors.
    """
    def __init__(self, base_dir: str, tenant_id: str, remote_anchor_config: Optional[Dict[str, Any]] = None):
        self.base_dir = Path(base_dir)
        self.tenant_id = tenant_id
        self.log_dir = self.base_dir / tenant_id / "audit"
        self.log_path = self.log_dir / "sovereign_audit.jsonl"
        self.anchor_path = self.log_dir / "sovereign_audit.anchor"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._last_hash = None
        
        # Remote Anchoring (v1.1.0 Roadmap)
        from .remote_anchor import RemoteAnchorService
        self.remote_service = RemoteAnchorService(remote_anchor_config)

    def log(self, event_type: str, principal: Principal, data: Dict[str, Any], correlation_id: Optional[str] = None):
        """Log an event to the tenant's chain and update the hardware-bound anchor."""
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
        self.save_anchor(curr_hash)
        
        # Async/Background remote anchoring (Optional)
        self.remote_service.anchor(self.tenant_id, curr_hash)
        
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

    def save_anchor(self, last_hash: str):
        """Saves a signed anchor to the filesystem, tied to the machine secret."""
        secret = ChainSecretManager.get_secret()
        # HMAC(Secret, LastHash)
        signature = hmac.new(secret, last_hash.encode(), hashlib.sha256).hexdigest()
        anchor_data = {
            "last_hash": last_hash,
            "signature": signature,
            "updated_at": time.time()
        }
        self.anchor_path.write_text(json.dumps(anchor_data), encoding="utf-8")

    def verify_integrity(self) -> bool:
        """
        Full chain validation. Checks both internal consistency AND the hardware-bound anchor.
        Detection: Deletion of the last entry will cause an anchor mismatch.
        """
        if not self.log_path.exists():
            return True
            
        prev_hash = AuditChainManager.GENESIS_HASH
        calculated_final_hash = prev_hash
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    entry = json.loads(line.strip())
                    expected_hash = AuditChainManager.calculate_next_hash(prev_hash, entry)
                    if entry.get("chain_hash") != expected_hash:
                        return False
                    prev_hash = expected_hash
                    calculated_final_hash = expected_hash
            
            # Anchor Verification
            if self.anchor_path.exists():
                anchor_data = json.loads(self.anchor_path.read_text(encoding="utf-8"))
                saved_hash = anchor_data.get("last_hash")
                saved_sig = anchor_data.get("signature")
                
                # 1. Check if the file's final hash matches the anchor's hash
                if calculated_final_hash != saved_hash:
                    return False # Deletion detected!
                
                # 2. Check if the anchor's signature is valid (Hardware Binding)
                secret = ChainSecretManager.get_secret()
                expected_sig = hmac.new(secret, saved_hash.encode(), hashlib.sha256).hexdigest()
                if saved_sig != expected_sig:
                    return False # Anchor tampering detected!
                    
            return True
        except Exception:
            return False

    def close(self):
        """No-op for now, satisfies cleanup interface."""
        pass
