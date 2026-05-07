import pytest
import json
import os
from pathlib import Path
from sovereign_ai.common.audit import SovereignAuditLogger, Principal
from sovereign_ai.rag.schemas import PolicyDecision

@pytest.fixture
def audit_log(tmp_path):
    # Use a mock principal for testing
    return SovereignAuditLogger(base_dir=str(tmp_path), tenant_id="test_tamper")

def test_chain_generation_and_valid_verification(audit_log):
    # Log 3 records
    for i in range(3):
        audit_log.log("test", f"EVT_{i}", "admin", {"seq": i})
    
    # Verification is done on the managed chain
    is_valid = audit_log.chain.verify_chain()
    assert is_valid

def test_detect_content_tampering(audit_log):
    # 1. Setup valid chain
    for i in range(3):
        audit_log.log("test", f"EVT_{i}", "admin", {"seq": i})
        
    # 2. Tamper with the SECOND record's content
    log_path = audit_log.chain.audit_file
    with open(log_path, "r") as f:
        lines = f.readlines()
    
    data = json.loads(lines[1])
    data["principal"] = "malicious-actor" # Change content
    lines[1] = json.dumps(data) + "\n"
    
    with open(log_path, "w") as f:
        f.writelines(lines)
        
    # 3. Verify
    is_valid = audit_log.chain.verify_chain()
    assert not is_valid

def test_detect_sequence_gap(audit_log):
    # 1. Setup valid chain
    for i in range(3):
        audit_log.log("test", f"EVT_{i}", "admin", {"seq": i})
        
    # 2. Delete the middle record
    log_path = audit_log.chain.audit_file
    with open(log_path, "r") as f:
        lines = f.readlines()
    
    del lines[1]
    
    with open(log_path, "w") as f:
        f.writelines(lines)
        
    # 3. Verify
    is_valid = audit_log.chain.verify_chain()
    assert not is_valid

def test_detect_hash_chain_break(audit_log):
    # 1. Setup valid chain
    for i in range(3):
        audit_log.log("test", f"EVT_{i}", "admin", {"seq": i})
        
    # 2. Swap records 2 and 3 (Sequence will be 0, 2, 1)
    log_path = audit_log.chain.audit_file
    with open(log_path, "r") as f:
        lines = f.readlines()
    
    lines[1], lines[2] = lines[2], lines[1]
    
    with open(log_path, "w") as f:
        f.writelines(lines)
        
    # 3. Verify
    is_valid = audit_log.chain.verify_chain()
    assert not is_valid

def test_detect_malformed_json(audit_log):
    audit_log.log("test", "EVT_0", "admin", {"seq": 0})
    
    log_path = audit_log.chain.audit_file
    with open(log_path, "a") as f:
        f.write("not a json line\n")
        
    is_valid = audit_log.chain.verify_chain()
    assert not is_valid
