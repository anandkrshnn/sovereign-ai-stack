import json
from pathlib import Path
from typing import List, Dict, Optional
from ...common.audit import SignedAuditChain

class AuditChainManager:
    """
    Unified Forensic Audit Chain Manager.
    Delegates to SignedAuditChain for Ed25519 asymmetric signatures.
    """
    
    GENESIS_HASH = "0" * 64

    @staticmethod
    def calculate_next_hash(prev_hash: str, entry: dict) -> str:
        # We reuse the logic from SignedAuditChain if needed, 
        # but AuditChainManager is now mostly used for verification of existing logs.
        # For appending, use SignedAuditChain instance.
        import hashlib
        entry_copy = entry.copy()
        entry_copy.pop("curr_hash", None)
        entry_copy.pop("chain_hash", None) # Support both legacy and new naming
        
        canonical = json.dumps(entry_copy, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(f"{prev_hash}{canonical}".encode()).hexdigest()

    @staticmethod
    def save_anchor(log_path: Path, key_manager=None, last_hash: str = None):
        """
        Saves the final stable hash of the chain to an out-of-band anchor file.
        In the new version, we prefer full chain signatures, but we keep this for 
        backward compatibility with simple hash-anchoring.
        """
        log_path = log_path.absolute()
        if last_hash is None:
            last_hash = AuditChainManager.get_last_hash(log_path)
            
        anchor_path = log_path.with_suffix(".anchor")
        anchor_path.write_text(last_hash, encoding="utf-8")

    @staticmethod
    def verify_chain(log_path: Path, **kwargs) -> bool:
        """Delegates to the robust SignedAuditChain verifier."""
        chain = SignedAuditChain(tenant_id="forensic_check", audit_file=log_path)
        return chain.verify_chain()

    @staticmethod
    def get_last_hash(log_path: Path) -> str:
        """Retrieve last hash using O(1) seeker."""
        record = SignedAuditChain._get_last_record_fast(log_path)
        if record:
            return record.get("curr_hash") or record.get("chain_hash")
        return AuditChainManager.GENESIS_HASH
