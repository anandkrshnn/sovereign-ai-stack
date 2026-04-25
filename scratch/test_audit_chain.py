import json
import os
from pathlib import Path
import hashlib

def calculate_next_hash(prev_hash: str, entry: dict) -> str:
    entry_copy = entry.copy()
    entry_copy.pop("chain_hash", None)
    canonical = json.dumps(entry_copy, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(f"{prev_hash}{canonical}".encode()).hexdigest()

def verify_chain(log_path: str) -> bool:
    if not os.path.exists(log_path):
        print(f"Error: Audit log not found at {log_path}")
        return False
        
    print(f"Checking audit log: {log_path}")
    prev_hash = "genesis"
    
    with open(log_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            entry = json.loads(line.strip())
            expected_hash = calculate_next_hash(prev_hash, entry)
            
            if entry.get("chain_hash") != expected_hash:
                print(f"❌ Chain broken at sequence {i}!")
                print(f"Expected: {expected_hash}")
                print(f"Found:    {entry.get('chain_hash')}")
                return False
            
            prev_hash = expected_hash
            
    return True

if __name__ == "__main__":
    # Test with the default tenant's audit log
    audit_log = "data/default/audit/sovereign_audit.jsonl"
    if verify_chain(audit_log):
        print("Unified Audit Chain Verified: 100% Integrity.")
    else:
        print("Audit Chain Verification Failed.")
