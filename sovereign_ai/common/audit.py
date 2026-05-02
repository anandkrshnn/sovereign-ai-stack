"""
Forensic Audit Chain with Ed25519 Signatures

Provides tamper-evident audit trail with asymmetric cryptography.
Every event is signed with Ed25519 private key, verifiable by anyone with public key.
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization


@dataclass
class AuditEvent:
    """Single event in the audit chain."""
    
    sequence_number: int
    timestamp: str
    component: str
    action: str
    principal: str
    tenant_id: str
    
    # Event-specific data
    event_data: Dict[str, Any]
    
    # Chain linking
    prev_hash: str
    curr_hash: str
    
    # Ed25519 signature (NEW)
    signature: str  # Base64-encoded Ed25519 signature
    public_key: str  # Base64-encoded Ed25519 public key


class SignedAuditChain:
    """
    Audit chain with Ed25519 asymmetric signatures.
    
    Every event is:
    1. Canonically serialized (sorted JSON)
    2. SHA-256 hashed (chain linking)
    3. Ed25519 signed (tamper-proof)
    
    Verification requires only the public key (not private key).
    """
    
    def __init__(
        self,
        tenant_id: str,
        audit_file: Path,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None
    ):
        """
        Initialize audit chain with Ed25519 signing capability.
        
        Args:
            tenant_id: Tenant identifier
            audit_file: Path to JSONL audit log file
            signing_key: Ed25519 private key (generate if None)
        """
        self.tenant_id = tenant_id
        self.audit_file = Path(audit_file)
        
        # Generate or use provided signing key
        if signing_key is None:
            self.signing_key = ed25519.Ed25519PrivateKey.generate()
        else:
            self.signing_key = signing_key
        
        # Derive public key
        self.public_key = self.signing_key.public_key()
        
        # Initialize chain
        self.sequence_number = 0
        self.last_hash = "0" * 64  # Genesis hash
        
        # Load existing chain if present
        if self.audit_file.exists():
            self._load_chain()
    
    def _canonical_json(self, event: Dict[str, Any]) -> bytes:
        """
        Create canonical JSON representation for signing.
        
        Excludes signature and curr_hash (which depend on signature).
        """
        # Create signing payload (without signature/curr_hash)
        signing_data = {
            "sequence_number": event["sequence_number"],
            "timestamp": event["timestamp"],
            "component": event["component"],
            "action": event["action"],
            "principal": event["principal"],
            "tenant_id": event["tenant_id"],
            "event_data": event["event_data"],
            "prev_hash": event["prev_hash"],
        }
        
        # Canonical JSON (sorted keys, no whitespace)
        canonical = json.dumps(signing_data, sort_keys=True, separators=(',', ':'))
        return canonical.encode('utf-8')
    
    def _sign_event(self, event: Dict[str, Any]) -> str:
        """
        Sign event with Ed25519 private key.
        
        Returns base64-encoded signature.
        """
        canonical = self._canonical_json(event)
        signature_bytes = self.signing_key.sign(canonical)
        
        # Base64 encode for JSON storage
        import base64
        return base64.b64encode(signature_bytes).decode('utf-8')
    
    def _hash_event(self, event: Dict[str, Any]) -> str:
        """
        Compute SHA-256 hash of event (including signature).
        
        This creates the chain link for the next event.
        """
        # Hash the complete event (including signature)
        canonical = json.dumps(event, sort_keys=True, separators=(',', ':')).encode('utf-8')
        return hashlib.sha256(canonical).hexdigest()
    
    def log_event(
        self,
        component: str,
        action: str,
        principal: str,
        event_data: Dict[str, Any]
    ) -> AuditEvent:
        """
        Log event to audit chain with Ed25519 signature.
        
        Process:
        1. Create event dict with prev_hash
        2. Sign canonical JSON → signature
        3. Hash complete event (including signature) → curr_hash
        4. Append to chain file
        """
        self.sequence_number += 1
        
        # 1. Create event
        event = {
            "sequence_number": self.sequence_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "action": action,
            "principal": principal,
            "tenant_id": self.tenant_id,
            "event_data": event_data,
            "prev_hash": self.last_hash,
        }
        
        # 2. Sign event
        signature = self._sign_event(event)
        event["signature"] = signature
        
        # 3. Add public key (for verification)
        public_key_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        import base64
        event["public_key"] = base64.b64encode(public_key_bytes).decode('utf-8')
        
        # 4. Hash complete event (creates chain link)
        curr_hash = self._hash_event(event)
        event["curr_hash"] = curr_hash
        
        # 5. Update state
        self.last_hash = curr_hash
        
        # 6. Write to file
        self._append_to_file(event)
        
        # 7. Return typed event
        return AuditEvent(**event)
    
    def _append_to_file(self, event: Dict[str, Any]):
        """Append event to JSONL audit file."""
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.audit_file, 'a') as f:
            f.write(json.dumps(event) + '\n')
    
    def _load_chain(self):
        """Load existing chain and set sequence number + last hash."""
        events = []
        
        with open(self.audit_file, 'r') as f:
            for line in f:
                if line.strip():
                    events.append(json.loads(line))
        
        if events:
            last_event = events[-1]
            self.sequence_number = last_event["sequence_number"]
            self.last_hash = last_event["curr_hash"]
    
    def verify_chain(self, events: Optional[List[Dict[str, Any]]] = None) -> bool:
        """
        Verify integrity of entire audit chain.
        
        Checks:
        1. Hash chain integrity (curr_hash matches recomputed hash)
        2. Ed25519 signatures (all events validly signed)
        3. Sequence numbers (no gaps)
        
        Returns True if chain is valid, False otherwise.
        """
        if events is None:
            # Load from file
            if not self.audit_file.exists():
                return True  # Empty chain is valid
            
            events = []
            with open(self.audit_file, 'r') as f:
                for line in f:
                    if line.strip():
                        events.append(json.loads(line))
        
        if not events:
            return True
        
        prev_hash = "0" * 64  # Genesis
        
        for i, event in enumerate(events):
            # Check 1: Sequence number
            expected_seq = i + 1
            if event["sequence_number"] != expected_seq:
                print(f"❌ Sequence mismatch at event {i}: expected {expected_seq}, got {event['sequence_number']}")
                return False
            
            # Check 2: Hash chain
            if event["prev_hash"] != prev_hash:
                print(f"❌ Hash chain broken at event {i}")
                return False
            
            # Check 3: Ed25519 signature
            if not self._verify_signature(event):
                print(f"❌ Invalid signature at event {i}")
                return False
            
            # Check 4: Current hash matches recomputed
            recomputed_hash = self._hash_event(event)
            if event["curr_hash"] != recomputed_hash:
                print(f"❌ Current hash mismatch at event {i}")
                return False
            
            prev_hash = event["curr_hash"]
        
        return True
    
    def _verify_signature(self, event: Dict[str, Any]) -> bool:
        """
        Verify Ed25519 signature for a single event.
        
        Uses public key stored in event (allows external verification).
        """
        import base64
        
        try:
            # Extract signature and public key
            signature_b64 = event["signature"]
            public_key_b64 = event["public_key"]
            
            signature_bytes = base64.b64decode(signature_b64)
            public_key_bytes = base64.b64decode(public_key_b64)
            
            # Reconstruct public key
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
            
            # Get canonical payload
            canonical = self._canonical_json(event)
            
            # Verify signature
            public_key.verify(signature_bytes, canonical)
            return True
            
        except Exception as e:
            print(f"Signature verification failed: {e}")
            return False
    
    def export_public_key(self) -> str:
        """
        Export public key for external verification.
        
        Returns base64-encoded Ed25519 public key.
        """
        import base64
        public_key_bytes = self.public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        return base64.b64encode(public_key_bytes).decode('utf-8')


# Backward compatibility alias
AuditChainManager = SignedAuditChain

@dataclass
class Principal:
    """Unified identity principal for the Sovereign AI Stack."""
    id: str
    tenant_id: str = "default"
    roles: List[str] = __import__('dataclasses').field(default_factory=lambda: ["user"])
    classifications: List[str] = __import__('dataclasses').field(default_factory=lambda: ["public"])
    metadata: Dict[str, Any] = __import__('dataclasses').field(default_factory=dict)

    def to_dict(self):
        return asdict(self)

@dataclass
class AuditRecord:
    event_id: str
    timestamp: float
    correlation_id: str
    event_type: str
    principal: Dict[str, Any]
    data: Dict[str, Any]
    prev_hash: str
    chain_hash: Optional[str] = None

class SovereignAuditLogger:
    """Backward compatibility adapter for SignedAuditChain."""
    def __init__(self, base_dir: str, tenant_id: str, remote_anchor_config: Optional[Dict[str, Any]] = None):
        from .secure_key import SecureKeyManager
        self.base_dir = Path(base_dir)
        self.tenant_id = tenant_id
        self.log_dir = self.base_dir / tenant_id / "audit"
        self.log_path = self.log_dir / "sovereign_audit.jsonl"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self.key_mgr = SecureKeyManager(tenant_id)
        self.chain = SignedAuditChain(tenant_id, self.log_path, self.key_mgr.get_or_create_signing_key())

    def log(self, event_type: str, principal: Principal, data: Dict[str, Any], correlation_id: Optional[str] = None):
        event = self.chain.log_event(
            component="system",
            action=event_type,
            principal=principal.id,
            event_data=data
        )
        return event.curr_hash

    def verify_integrity(self) -> bool:
        return self.chain.verify_chain()

    def close(self):
        pass
