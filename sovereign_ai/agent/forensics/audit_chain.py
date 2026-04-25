import json
import hashlib
from pathlib import Path
from typing import List, Dict, Optional

class AuditChainManager:
    """
    Manages the cryptographic hash chain for decision_traces.jsonl.
    Enforces canonicalization and prevents non-repudiation.
    """
    
    GENESIS_HASH = "genesis"

    @staticmethod
    def calculate_next_hash(prev_hash: str, entry: dict) -> str:
        """
        Calculates the next hash using canonical JSON formatting.
        Canonicalization ensures key sorting and no whitespace.
        """
        # Remove any existing hash to ensure idempotency
        entry_copy = entry.copy()
        entry_copy.pop("chain_hash", None)
        
        canonical = json.dumps(entry_copy, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(f"{prev_hash}{canonical}".encode()).hexdigest()

    @staticmethod
    def save_anchor(log_path: Path, key_manager=None, last_hash: str = None):
        """Saves the final stable hash of the chain to an out-of-band anchor file."""
        log_path = log_path.absolute()
        if last_hash is None:
            last_hash = AuditChainManager.get_last_hash(log_path, key_manager=key_manager)
            
        anchor_path = log_path.with_suffix(".anchor")
        anchor_path.write_text(last_hash, encoding="utf-8")

    @staticmethod
    def verify_anchor(log_path: Path, key_manager=None, last_hash: str = None) -> bool:
        """Verifies the current terminal hash against the recorded anchor."""
        log_path = log_path.absolute()
        anchor_path = log_path.with_suffix(".anchor")
        if not anchor_path.exists():
            return False
        
        if last_hash is None:
            last_hash = AuditChainManager.get_last_hash(log_path, key_manager=key_manager)
            
        return anchor_path.read_text(encoding="utf-8") == last_hash

    @staticmethod
    def verify_chain(log_path: Path, check_anchor: bool = False, key_manager=None, mode: str = "plaintext", expected_start_hash: str = None) -> bool:
        """
        Full chain validation. Re-calculates every hash from genesis or a provided starting anchor.
        If mode="plaintext", fails fast on encrypted data.
        """
        if not log_path.exists():
            return True
            
        if mode == "encrypted" and not key_manager:
            raise ValueError("Forensic 'encrypted' mode requires an explicit key_manager.")

        prev_hash = expected_start_hash or AuditChainManager.GENESIS_HASH
        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                        
                    # Decrypt if mode="encrypted"
                    if mode == "encrypted":
                        line = key_manager.decrypt(line)
                    elif line.startswith("gAAAA"):
                        # Fail-Fast: Encrypted record found in Plaintext mode
                        return False
                            
                    entry = json.loads(line)
                    expected_hash = AuditChainManager.calculate_next_hash(prev_hash, entry)
                    
                    if entry.get("chain_hash") != expected_hash:
                        return False
                    prev_hash = expected_hash
            
            if check_anchor:
                return AuditChainManager.verify_anchor(log_path, key_manager=key_manager, last_hash=prev_hash)
                
            return True
        except Exception:
            return False

    @staticmethod
    def get_last_hash(log_path: Path, key_manager=None, mode: str = "plaintext", expected_start_hash: str = None) -> str:
        """
        Retrieves the hash of the last entry in the log for appending.
        If mode="plaintext", fails on encrypted files.
        """
        if not log_path.exists():
            return expected_start_hash or AuditChainManager.GENESIS_HASH
            
        if mode == "encrypted" and not key_manager:
            raise ValueError("Forensic 'encrypted' mode requires an explicit key_manager.")

        # Optimization (v5.0): Attempt high-performance backward-seek first
        fast_hash = AuditChainManager._get_last_hash_fast(log_path, key_manager=key_manager, mode=mode)
        if fast_hash:
            return fast_hash
            
        # Fallback to full-file read only if back-seek fails
        try:
            last_hash = AuditChainManager.GENESIS_HASH
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    if mode == "encrypted":
                        line = key_manager.decrypt(line)
                    elif line.startswith("gAAAA"):
                        return AuditChainManager.GENESIS_HASH # Fallback safely

                    entry = json.loads(line)
                    last_hash = entry.get("chain_hash", last_hash)
            return last_hash
        except Exception:
            return AuditChainManager.GENESIS_HASH

    @staticmethod
    def _get_last_hash_fast(log_path: Path, key_manager=None, mode: str = "plaintext", chunk_size: int = 16384) -> Optional[str]:
        """Backward-seek reader (v5.0): only reads the last chunk of the file (O(1))."""
        if not log_path.exists():
            return None
            
        try:
            with open(log_path, "rb") as f:
                f.seek(0, 2)  # Seek to end
                file_size = f.tell()
                if file_size == 0:
                    return AuditChainManager.GENESIS_HASH
                
                # Read last chunk
                offset = min(chunk_size, file_size)
                f.seek(-offset, 2)
                chunk = f.read(offset)
                
                # Decode and split lines
                lines = chunk.decode("utf-8", errors="ignore").splitlines()
                
                for line in reversed(lines):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Decrypt if mode="encrypted"
                    if mode == "encrypted":
                        line = key_manager.decrypt(line)
                    elif line.startswith("gAAAA"):
                        return None # Fail on ciphertext in plaintext mode
                    
                    try:
                        entry = json.loads(line)
                        return entry.get("chain_hash")
                    except (json.JSONDecodeError, KeyError):
                        continue
            return None
        except Exception:
            return None
