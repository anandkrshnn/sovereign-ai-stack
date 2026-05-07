"""
Forensic Audit Chain with Ed25519 Signatures

Provides tamper-evident audit trail with asymmetric cryptography.
Every event is signed with Ed25519 private key, verifiable by anyone with public key.
"""

import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict, field

from cryptography.hazmat.primitives.asymmetric import ed25519, ec
from cryptography.hazmat.primitives import serialization, hashes
from .hardware_trust import SecureAnchor, SoftwareSimulatorAnchor, LegacyRawAnchor, WindowsTPMAnchor
from .schemas import SigningAlgorithm, RecordStatus


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
    algorithm: str = "ed25519"


class SecurityHalt(Exception):
    """Immediate safety halt when forensic integrity is compromised."""
    pass


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
        audit_file: str, 
        anchor: Optional[SecureAnchor] = None,
        signing_key: Optional[ed25519.Ed25519PrivateKey] = None
    ):
        """
        Initialize audit chain with Ed25519 signing capability.
        
        Args:
            tenant_id: Tenant identifier
            audit_file: Path to JSONL audit log file
            anchor: Secure hardware anchor (TPM/HSM)
            signing_key: Legacy Ed25519 private key (deprecated, use anchor)
        """
        self.tenant_id = tenant_id
        self.audit_file = Path(audit_file)
        
        if anchor:
            self.anchor = anchor
        elif signing_key:
            # Wrap legacy key
            self.anchor = LegacyRawAnchor(signing_key)
        else:
            # Default to software-bound anchor (simulated TPM)
            self.anchor = SoftwareSimulatorAnchor(tenant_id)
        
        print(f"DEBUG: anchor type for {tenant_id} is {type(self.anchor)}")
        
        # Derive public key from anchor
        self.public_key = self.anchor.get_public_key()
        
        # Initialize chain
        self.sequence_number = 0
        self.last_hash = "0" * 64  # Genesis hash
        self.pinned_algorithm: Optional[str] = None
        
        # 5. Checkpoint for truncation detection
        self.checkpoint_file = self.audit_file.with_suffix(".checkpoint")
        
        # Load existing chain if present
        if self.audit_file.exists():
            self._load_chain()
            self._verify_checkpoint()
    
    def _canonical_json(self, event: Dict[str, Any]) -> bytes:
        """Create canonical JSON representation for signing."""
        signing_data = {
            "sequence_number": event["sequence_number"],
            "timestamp": event["timestamp"],
            "component": event["component"],
            "action": event["action"],
            "principal": event["principal"],
            "tenant_id": event["tenant_id"],
            "event_data": event["event_data"],
            "prev_hash": event["prev_hash"],
            "algorithm": event.get("algorithm", "ed25519"), # Include algorithm in signature
        }
        return json.dumps(signing_data, sort_keys=True, separators=(',', ':')).encode('utf-8')

    @staticmethod
    def _get_last_record_fast(file_path: Path, chunk_size: int = 8192) -> Optional[Dict[str, Any]]:
        """Backward-seek reader (v5.0): only reads the last chunk of the file (O(1))."""
        if not file_path.exists():
            return None
            
        try:
            with open(file_path, "rb") as f:
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()
                if file_size == 0:
                    return None
                
                offset = min(chunk_size, file_size)
                f.seek(-offset, 2)
                chunk = f.read(offset)
                
                lines = chunk.decode("utf-8", errors="ignore").splitlines()
                for line in reversed(lines):
                    line = line.strip()
                    if not line: continue
                    try:
                        return json.loads(line)
                    except json.JSONDecodeError:
                        continue
            return None
        except Exception:
            return None
    
    def _sign_event(self, event: Dict[str, Any]) -> str:
        """
        Sign event using the Secure Anchor (TPM/HSM).
        """
        canonical = self._canonical_json(event)
        signature_bytes = self.anchor.sign(canonical)
        
        # Base64 encode for JSON storage
        import base64
        return base64.b64encode(signature_bytes).decode('utf-8')
    
    def _hash_event(self, event: Dict[str, Any]) -> str:
        """
        Compute SHA-256 hash of event (including signature).
        
        This creates the chain link for the next event.
        """
        event_copy = event.copy()
        event_copy.pop("curr_hash", None)
        # Hash the complete event (including signature)
        canonical = json.dumps(event_copy, sort_keys=True, separators=(',', ':')).encode('utf-8')
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
        
        # 1. Create event object
        event = {
            "sequence_number": self.sequence_number,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "component": component,
            "action": action,
            "principal": principal,
            "tenant_id": self.tenant_id,
            "event_data": event_data,
            "prev_hash": self.last_hash,
            "algorithm": self.anchor.algorithm.value,
        }
        
        # Enforce pinned algorithm or lock it in
        if self.pinned_algorithm:
            if event["algorithm"] != self.pinned_algorithm:
                # If algorithm changed, this should be a GENESIS block linking back
                if action != "GENESIS_TRANSITION":
                    raise RuntimeError(f"Algorithm mismatch: chain pinned to {self.pinned_algorithm}, anchor uses {event['algorithm']}")
        else:
            self.pinned_algorithm = event["algorithm"]
        
        # 2. Add public key for independent verification
        public_key_bytes = self.anchor.get_public_key().public_bytes(
            encoding=serialization.Encoding.Raw if self.anchor.algorithm == SigningAlgorithm.ED25519
            else serialization.Encoding.X962,
            format=serialization.PublicFormat.Raw if self.anchor.algorithm == SigningAlgorithm.ED25519
            else serialization.PublicFormat.UncompressedPoint
        )
        import base64
        event["public_key"] = base64.b64encode(public_key_bytes).decode('utf-8')
        
        # 3. Sign the canonical JSON
        event["signature"] = self._sign_event(event)
        
        # 4. Hash complete event (creates chain link)
        curr_hash = self._hash_event(event)
        event["curr_hash"] = curr_hash
        self.last_hash = curr_hash
        
        # 5. Persist to file
        with open(self.audit_file, "a") as f:
            f.write(json.dumps(event) + "\n")
            
        # 6. Update checkpoint (truncation protection)
        self._save_checkpoint()
        
        # 7. Return typed event
        return AuditEvent(**event)
    
    def _append_to_file(self, event: Dict[str, Any]):
        """Append event to JSONL audit file."""
        self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.audit_file, 'a') as f:
            f.write(json.dumps(event) + '\n')
    
    def _load_chain(self):
        """Load existing chain state (O(1) optimization)."""
        last_record = self._get_last_record_fast(self.audit_file)
        if last_record:
            self.sequence_number = last_record["sequence_number"]
            self.last_hash = last_record["curr_hash"]
            # Detect algorithm from the first record if possible, or use the last one
            # For robustness, we should read the first record to pin the algorithm
            self.pinned_algorithm = last_record.get("algorithm", "ed25519")
        else:
            self.sequence_number = 0
            self.last_hash = "0" * 64
    
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
                print(f"Sequence mismatch at event {i}: expected {expected_seq}, got {event['sequence_number']}")
                return False
            
            # Check 2: Hash chain
            if event["prev_hash"] != prev_hash:
                print(f"Hash chain broken at event {i}")
                return False
            
            # Check 3: Ed25519 signature
            if not self._verify_signature(event):
                print(f"Invalid signature at event {i}")
                return False
            
            # Check 4: Current hash matches recomputed
            recomputed_hash = self._hash_event(event)
            if event["curr_hash"] != recomputed_hash:
                print(f"Current hash mismatch at event {i}")
                return False
            
            prev_hash = event["curr_hash"]
        
        return True
    
    def _verify_signature(self, event: Dict[str, Any]) -> bool:
        """
        Verify signature for a single event based on stored algorithm.
        """
        import base64
        from cryptography.exceptions import InvalidSignature
        
        try:
            algorithm = event.get("algorithm", "ed25519")
            
            # [Finding 2 Fix] Pin algorithm to prevent confusion attacks
            if self.pinned_algorithm and algorithm != self.pinned_algorithm:
                # Only exception is a GENESIS transition record which is signed by the NEW key
                # but might be verifying an old chain. 
                # Actually, the hardening rule is: ALL records in this file must use the SAME algo.
                print(f"Algorithm mismatch: expected {self.pinned_algorithm}, got {algorithm}")
                return False

            signature_b64 = event["signature"]
            public_key_b64 = event["public_key"]
            
            signature_bytes = base64.b64decode(signature_b64)
            public_key_bytes = base64.b64decode(public_key_b64)
            
            canonical_data = self._canonical_json(event)
            
            if algorithm == "ed25519":
                pub = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
                pub.verify(signature_bytes, canonical_data)
            elif algorithm == "p256":
                pub = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public_key_bytes)
                pub.verify(signature_bytes, canonical_data, ec.ECDSA(hashes.SHA256()))
            else:
                print(f"Unsupported algorithm: {algorithm}")
                return False
                
            return True
        except InvalidSignature:
            return False
        except Exception as e:
            print(f"Signature verification error: {e}")
            return False

    def read_logs(self) -> List[Dict[str, Any]]:
        """Read all events from the audit log."""
        if not self.audit_file.exists():
            return []
            
        events = []
        with open(self.audit_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return events
    
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

    def _save_checkpoint(self):
        """Save the high-water mark to a separate file to detect truncation."""
        checkpoint = {
            "last_sequence": self.sequence_number,
            "last_hash": self.last_hash,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        with open(self.checkpoint_file, "w") as f:
            json.dump(checkpoint, f)

    def _verify_checkpoint(self):
        """Verify that the audit file has not been truncated since the last checkpoint."""
        if not self.checkpoint_file.exists():
            # If no checkpoint exists, we are in legacy mode or first run
            return
            
        try:
            with open(self.checkpoint_file, "r") as f:
                checkpoint = json.load(f)
                
            if self.sequence_number < checkpoint["last_sequence"]:
                raise SecurityHalt(
                    f"FORENSIC_TRUNCATION_DETECTED: Audit log is shorter than checkpoint! "
                    f"Expected seq >= {checkpoint['last_sequence']}, got {self.sequence_number}. "
                    "This indicates a potential attempt to hide agent activity."
                )
            
            if self.sequence_number == checkpoint["last_sequence"]:
                if self.last_hash != checkpoint["last_hash"]:
                     raise SecurityHalt("FORENSIC_TAMPERING_DETECTED: Last hash mismatch with checkpoint!")
        except (json.JSONDecodeError, KeyError):
            import logging
            logging.getLogger(__name__).warning("Corrupt checkpoint file detected.")


# Backward compatibility alias
AuditChainManager = SignedAuditChain

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
    def __init__(self, base_dir: str, tenant_id: str, anchor: Optional[SecureAnchor] = None, remote_anchor_config: Optional[Dict[str, Any]] = None):
        from .secure_key import SecureKeyManager
        self.base_dir = Path(base_dir)
        self.tenant_id = tenant_id
        self.log_dir = self.base_dir / tenant_id / "audit"
        self.log_path = self.log_dir / "sovereign_audit.jsonl"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        if anchor:
            self.chain = SignedAuditChain(
                tenant_id=tenant_id,
                audit_file=str(self.log_path),
                anchor=anchor
            )
        else:
            self.key_mgr = SecureKeyManager(tenant_id)
            self.chain = SignedAuditChain(
                tenant_id=tenant_id, 
                audit_file=str(self.log_path), 
                signing_key=self.key_mgr.get_or_create_signing_key()
            )

    def log(self, event_type: str, principal: Principal, data: Dict[str, Any], correlation_id: Optional[str] = None):
        event = self.chain.log_event(
            component="system",
            action=event_type,
            principal=principal.id,
            event_data=data
        )
        return event.curr_hash

    def read_logs(self) -> List[Dict[str, Any]]:
        return self.chain.read_logs()

    def verify_integrity(self) -> Tuple[bool, str]:
        valid = self.chain.verify_chain()
        msg = "Forensic Integrity Verified" if valid else "Tampering Detected"
        return valid, msg

    def get_provider_status(self) -> Dict[str, Any]:
        """Diagnostic: Check key management capabilities."""
        status = self.chain.anchor.get_status()
        return {
            "type": status.get("type", "unknown"),
            "available": status.get("available", False),
            "backend": status.get("details", "N/A")
        }

    def close(self):
        pass
