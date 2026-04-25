import json
import os
import time
import hashlib
from typing import Dict, Any, Optional, Tuple

class AuditLogger:
    """
    Sovereign Bridge Audit Logger - Implementing GAIP-2030 Master Forensic Chain.
    
    Provides a hash-chained (SHA-256) master log that anchors evidence from 
    both retrieval (local-rag) and action (local-agent) layers.
    """
    
    def __init__(self, base_dir: str = "data", tenant_id: str = "default"):
        self.base_dir = base_dir
        self.tenant_id = tenant_id
        
        # Physical Isolation: /{base_dir}/{tenant_id}/audit.jsonl
        tenant_root = os.path.join(base_dir, tenant_id)
        if not os.path.exists(tenant_root):
            os.makedirs(tenant_root, exist_ok=True)
            
        self.log_path = os.path.join(tenant_root, "audit.jsonl")
        self._ensure_log_exists()

    def _ensure_log_exists(self):
        if not os.path.exists(self.log_path):
            with open(self.log_path, "w", encoding="utf-8") as f:
                pass

    def _get_last_record(self) -> Tuple[Optional[str], int]:
        """Retrieve the hash and sequence number of the last record."""
        if os.path.getsize(self.log_path) == 0:
            return None, 0
            
        with open(self.log_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            if f.tell() == 0:
                return None, 0
            
            # Read last line
            f.seek(max(0, f.tell() - 4096), os.SEEK_SET)
            lines = f.readlines()
            if not lines:
                return None, 0
            last_line = lines[-1].decode("utf-8").strip()
            if not last_line:
                return None, 0
            
            record = json.loads(last_line)
            return record.get("curr_hash"), record.get("sequence_number", 0)

    def log(
        self, 
        request_id: str, 
        principal: str, 
        rag_event_id: Optional[str] = None, 
        agent_trace_id: Optional[str] = None,
        outcome: str = "success"
    ) -> str:
        """
        Record a master session event into the hash chain.
        """
        print(f"DEBUG: AuditLogger.log() called for tenant {self.tenant_id} at {self.log_path}")
        prev_hash, last_seq = self._get_last_record()
        seq = last_seq + 1
        ts = time.time()
        
        # Prepare content for hashing
        content = {
            "sequence_number": seq,
            "timestamp": ts,
            "request_id": request_id,
            "principal": principal,
            "rag_event_id": rag_event_id,
            "agent_trace_id": agent_trace_id,
            "outcome": outcome,
            "prev_hash": prev_hash
        }
        
        # Compute SHA-256 Hash
        canonical_content = json.dumps(content, sort_keys=True)
        curr_hash = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()
        
        # Append to log
        record = content.copy()
        record["curr_hash"] = curr_hash
        
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()
            os.fsync(f.fileno())
            
        return curr_hash

    def verify_integrity(self) -> Tuple[bool, str]:
        """
        Verify the continuity and cryptographic integrity of the forensic chain.
        """
        if not os.path.exists(self.log_path) or os.path.getsize(self.log_path) == 0:
            return True, "Forensic chain is empty (initial state)."

        expected_prev_hash = None
        expected_seq = 1
        
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line)
                    
                    # 1. Sequence Check
                    if record.get("sequence_number") != expected_seq:
                        return False, f"Sequence Break at line {line_num}: Expected {expected_seq}, got {record.get('sequence_number')}"
                    
                    # 2. Continuity Check (prev_hash match)
                    if record.get("prev_hash") != expected_prev_hash:
                        return False, f"Continuity Break at line {line_num}: Hash chain link is broken."
                    
                    # 3. Cryptographic Verification
                    content = record.copy()
                    curr_hash = content.pop("curr_hash")
                    canonical_content = json.dumps(content, sort_keys=True)
                    recomputed_hash = hashlib.sha256(canonical_content.encode("utf-8")).hexdigest()
                    
                    if recomputed_hash != curr_hash:
                        return False, f"Tamper detected at line {line_num}: Content hash mismatch."
                    
                    # Prepare for next record
                    expected_prev_hash = curr_hash
                    expected_seq += 1
                    
                except Exception as e:
                    return False, f"Parse error at line {line_num}: {e}"
                    
        return True, f"Integrity Verified: Forensic chain intact ({expected_seq - 1} records)."
