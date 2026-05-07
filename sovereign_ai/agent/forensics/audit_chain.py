import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from ...common.audit import SignedAuditChain

class AuditChainManager:
    """
    Unified Forensic Audit Chain Manager.
    Delegates to SignedAuditChain for asymmetric signatures and robust verification.
    """
    
    GENESIS_HASH = "0" * 64

    @staticmethod
    def calculate_next_hash(prev_hash: str, entry: dict) -> str:
        """Deterministic SHA-256 link calculation for legacy compatibility."""
        import hashlib
        entry_copy = {k: v for k, v in entry.items() if k not in ("curr_hash", "chain_hash", "signature")}
        
        canonical = json.dumps(entry_copy, sort_keys=True)
        # Handle both (prev + canonical) and (prev_hash + canonical)
        return hashlib.sha256(f"{prev_hash}{canonical}".encode()).hexdigest()

    @staticmethod
    def save_anchor(log_path: Path, last_hash: str = None):
        """Saves the final stable hash of the chain to an out-of-band anchor file."""
        log_path = Path(log_path).absolute()
        if last_hash is None:
            last_hash = AuditChainManager.get_last_hash(log_path)
            
        anchor_path = log_path.with_suffix(".anchor")
        # Legacy format: just the hash string
        anchor_path.write_text(last_hash, encoding="utf-8")
        
        # Also update the modern checkpoint if possible
        chain = SignedAuditChain(tenant_id="legacy_bridge", audit_file=str(log_path))
        chain._save_checkpoint()

    @staticmethod
    def verify_anchor(log_path: Path, last_hash: str) -> bool:
        """Verifies the log against an out-of-band anchor file."""
        log_path = Path(log_path).absolute()
        anchor_path = log_path.with_suffix(".anchor")
        if not anchor_path.exists():
            return False
        
        stored_hash = anchor_path.read_text(encoding="utf-8").strip()
        current_hash = AuditChainManager.get_last_hash(log_path)
        
        # Verify both the passed last_hash and the stored anchor match current
        return stored_hash == last_hash == current_hash

    @staticmethod
    def verify_chain(log_path: Path, **kwargs) -> bool:
        """Delegates to the robust SignedAuditChain verifier."""
        chain = SignedAuditChain(tenant_id="forensic_check", audit_file=str(log_path))
        return chain.verify_chain()

    @staticmethod
    def get_last_hash(log_path: Path) -> str:
        """Retrieve last hash using O(1) seeker."""
        record = SignedAuditChain._get_last_record_fast(str(log_path))
        if record:
            return record.get("curr_hash") or record.get("chain_hash")
        return AuditChainManager.GENESIS_HASH
