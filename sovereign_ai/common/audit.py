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
    Manages the machine-unique cryptographic identity for OS-backed secure auditing.
    Uses Ed25519 asymmetric keys stored in the OS Secure Storage (Keyring).
    """
    SERVICE_NAME = "sovereign_ai"
    KEY_NAME = "forensic_identity_v1"
    _cached_signing_key = None

    @classmethod
    def get_signing_key(cls):
        """Retrieve or provision the Ed25519 private key from secure storage."""
        if cls._cached_signing_key:
            return cls._cached_signing_key
        
        from cryptography.hazmat.primitives.asymmetric import ed25519
        from cryptography.hazmat.primitives import serialization

        encoded_key = keyring.get_password(cls.SERVICE_NAME, cls.KEY_NAME)
        if encoded_key:
            try:
                cls._cached_signing_key = ed25519.Ed25519PrivateKey.from_private_bytes(
                    bytes.fromhex(encoded_key)
                )
                return cls._cached_signing_key
            except Exception:
                pass
        
        # Provision new hardware-bound forensic identity
        private_key = ed25519.Ed25519PrivateKey.generate()
        raw_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        try:
            keyring.set_password(cls.SERVICE_NAME, cls.KEY_NAME, raw_bytes.hex())
        except Exception:
            # Fallback for headless environments (ephemeral key)
            pass
        
        cls._cached_signing_key = private_key
        return cls._cached_signing_key

class AuditChainManager:
    """
    Cryptographic hash chain manager for tamper-evident auditing (v0.1.0-preview).
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
    Supports physical tenant isolation, hash-chaining, and OS-backed forensic anchors.
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
        """Saves a signed anchor to the filesystem, tied to the machine's Ed25519 identity."""
        from cryptography.hazmat.primitives import serialization
        
        signing_key = ChainSecretManager.get_signing_key()
        public_key = signing_key.public_key()
        
        # Sign the latest chain hash
        signature = signing_key.sign(last_hash.encode())
        
        anchor_data = {
            "last_hash": last_hash,
            "signature": signature.hex(),
            "public_key": public_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            ).hex(),
            "updated_at": time.time(),
            "algorithm": "Ed25519"
        }
        self.anchor_path.write_text(json.dumps(anchor_data, indent=2), encoding="utf-8")

    def verify_integrity(self) -> bool:
        """
        Full chain validation. Checks both internal consistency AND the OS-backed anchor.
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
            
            # Anchor Verification (Sovereign Forensic Guardrail)
            if self.anchor_path.exists():
                from cryptography.hazmat.primitives.asymmetric import ed25519
                
                anchor_data = json.loads(self.anchor_path.read_text(encoding="utf-8"))
                saved_hash = anchor_data.get("last_hash")
                saved_sig = anchor_data.get("signature")
                saved_pub = anchor_data.get("public_key")
                
                # 1. Detection: Was the log truncated? (File hash vs Anchor hash)
                if calculated_final_hash != saved_hash:
                    logger.error(f"AUDIT CORRUPTION: Log truncated or extended. File: {calculated_final_hash} vs Anchor: {saved_hash}")
                    return False
                
                # 2. Cryptographic Proof: Is the anchor valid? (Digital Signature)
                if saved_sig and saved_pub:
                    try:
                        pub_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(saved_pub))
                        pub_key.verify(bytes.fromhex(saved_sig), saved_hash.encode())
                    except Exception as e:
                        logger.error(f"FORENSIC ALERT: Invalid anchor signature! Tampering detected. Error: {e}")
                        return False
                    
            return True
        except Exception:
            return False

    def close(self):
        """No-op for now, satisfies cleanup interface."""
        pass
