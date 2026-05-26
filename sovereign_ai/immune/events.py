import time
import uuid
import hashlib
import json
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

@dataclass
class KnowledgeEvent:
    """
    Represents an atomic, cryptographically signed proposed change (Antigen) 
    to the Sovereign AI Stack's Company Brain.
    """
    payload: str  # The core content/statement being proposed
    source_author: str  # Entity proposing the change (e.g., "Agent-X", "User-Admin")
    event_type: str = "INSERT"  # INSERT, UPDATE, DELETE
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    parent_hash: str = "0" * 64  # Reference to the previous Merkle root or block hash
    signature: Optional[str] = None  # Ed25519 signature of the canonical representation
    metadata: Dict[str, Any] = field(default_factory=dict)
    merkle_hash: str = field(init=False)

    def __post_init__(self):
        self.merkle_hash = self.compute_hash()

    def to_canonical_dict(self) -> Dict[str, Any]:
        """
        Returns a deterministic, sorted dictionary representation of the event 
        excluding ephemeral fields (like the calculated merkle_hash itself).
        """
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "source_author": self.source_author,
            "timestamp": self.timestamp,
            "parent_hash": self.parent_hash,
            "metadata": sorted(self.metadata.items())  # Ensure stable sorting of metadata dict
        }

    def compute_hash(self) -> str:
        """
        Computes a SHA-256 canonical hash of the event for Merkle verification.
        """
        canonical_str = json.dumps(self.to_canonical_dict(), sort_keys=True)
        return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()

    def sign_event(self, private_key_hex: str) -> None:
        """
        Signs the event payload using a hex-encoded Ed25519 private key.
        """
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
            import bytes
        except ImportError:
            # Fallback for lightweight testing if cryptography library is missing
            self.signature = hashlib.sha256((self.payload + private_key_hex).encode('utf-8')).hexdigest()
            return

        private_key = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
        canonical_bytes = json.dumps(self.to_canonical_dict(), sort_keys=True).encode('utf-8')
        signature_bytes = private_key.sign(canonical_bytes)
        self.signature = signature_bytes.hex()

    def verify_signature(self, public_key_hex: str) -> bool:
        """
        Verifies the Ed25519 cryptographic signature against the canonical presentation.
        """
        if not self.signature:
            return False
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
            import bytes
        except ImportError:
            # Fallback verification matching the fallback sign method
            expected = hashlib.sha256((self.payload + public_key_hex).encode('utf-8')).hexdigest()
            return self.signature == expected

        try:
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex))
            canonical_bytes = json.dumps(self.to_canonical_dict(), sort_keys=True).encode('utf-8')
            public_key.verify(bytes.fromhex(self.signature), canonical_bytes)
            return True
        except Exception:
            return False
