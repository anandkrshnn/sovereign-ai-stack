import pytest
import json
import os
from pathlib import Path
from local_rag.audit import AuditLogger
from local_rag.schemas import AuditRecord, PolicyDecision

@pytest.fixture
def audit_log(tmp_path):
    log_path = tmp_path / "audit.jsonl"
    return AuditLogger(str(log_path))

def create_mock_record(seq, prev_hash=None):
    decision = PolicyDecision(action="allow", reason="Test")
    return AuditRecord(
        sequence_number=seq,
        event_id=f"evt-{seq}",
        principal="test-user",
        query_hash="hash",
        query_preview="hello",
        decision=decision,
        candidate_count=1,
        allowed_count=1,
        denied_count=0,
        prev_hash=prev_hash
    )

def test_chain_generation_and_valid_verification(audit_log):
    # Log 3 records
    for _ in range(3):
        rec = create_mock_record(0) # Logic inside log() handles seq and hashes
        audit_log.log(rec)
    
    is_valid, msg = audit_log.verify_integrity()
    assert is_valid
    assert "chain intact (3 records)" in msg.lower()

def test_detect_content_tampering(audit_log):
    # 1. Setup valid chain
    for _ in range(3):
        audit_log.log(create_mock_record(0))
        
    # 2. Tamper with the SECOND record's content
    with open(audit_log.log_path, "r") as f:
        lines = f.readlines()
    
    data = json.loads(lines[1])
    data["principal"] = "malicious-actor" # Change content
    lines[1] = json.dumps(data) + "\n"
    
    with open(audit_log.log_path, "w") as f:
        f.writelines(lines)
        
    # 3. Verify
    is_valid, msg = audit_log.verify_integrity()
    assert not is_valid
    assert "tampering detected" in msg.lower()
    assert "Line 2" in msg

def test_detect_sequence_gap(audit_log):
    # 1. Setup valid chain
    for _ in range(3):
        audit_log.log(create_mock_record(0))
        
    # 2. Delete the middle record
    with open(audit_log.log_path, "r") as f:
        lines = f.readlines()
    
    del lines[1]
    
    with open(audit_log.log_path, "w") as f:
        f.writelines(lines)
        
    # 3. Verify
    is_valid, msg = audit_log.verify_integrity()
    assert not is_valid
    assert "sequence gap" in msg.lower()

def test_detect_hash_chain_break(audit_log):
    # 1. Setup valid chain
    for _ in range(3):
        audit_log.log(create_mock_record(0))
        
    # 2. Swap records 2 and 3 (Sequence will be 0, 2, 1)
    with open(audit_log.log_path, "r") as f:
        lines = f.readlines()
    
    lines[1], lines[2] = lines[2], lines[1]
    
    with open(audit_log.log_path, "w") as f:
        f.writelines(lines)
        
    # 3. Verify
    is_valid, msg = audit_log.verify_integrity()
    assert not is_valid
    # Could be sequence gap or hash break depending on which check hits first
    assert ("sequence gap" in msg.lower() or "hash chain broken" in msg.lower())

def test_detect_malformed_json(audit_log):
    audit_log.log(create_mock_record(0))
    
    with open(audit_log.log_path, "a") as f:
        f.write("not a json line\n")
        
    is_valid, msg = audit_log.verify_integrity()
    assert not is_valid
    assert "malformed json" in msg.lower()
