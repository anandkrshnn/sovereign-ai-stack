import os
import json
import pytest
import tempfile
from pathlib import Path
from sovereign_ai.common.audit import SignedAuditChain
from sovereign_ai.common.merkle import MerkleTree

@pytest.fixture
def temp_audit_env():
    with tempfile.TemporaryDirectory() as temp_dir:
        audit_file = Path(temp_dir) / "test_audit.jsonl"
        chain = SignedAuditChain(tenant_id="test_tenant", audit_file=str(audit_file))
        yield chain, audit_file

def test_merkle_inclusion_and_tamper_detection(temp_audit_env):
    chain, audit_file = temp_audit_env
    
    # Generate exactly enough events to trigger a checkpoint (checkpoint_interval=10)
    # The 10th event triggers the MERKLE_CHECKPOINT, making 11 events total
    for i in range(1, 11):
        chain.log_event("system", f"action_{i}", "admin", {"data": i})
        
    # Retrieve proof for event 5
    proof_data = chain.get_audit_proof(5)
    
    # 1. Verify Inclusion Proof
    is_valid = MerkleTree.verify_proof(
        proof_data["leaf"], 
        proof_data["proof"], 
        proof_data["root"]
    )
    assert is_valid, "Merkle inclusion proof failed for valid event"
    
    # 2. Tamper Detection (Exclusion/Failure)
    # Tamper with the leaf hash
    tampered_leaf = proof_data["leaf"][:-4] + "dead"
    is_valid_tampered = MerkleTree.verify_proof(
        tampered_leaf,
        proof_data["proof"],
        proof_data["root"]
    )
    assert not is_valid_tampered, "Merkle tree failed to detect leaf tampering"

def test_merkle_proof_manipulation(temp_audit_env):
    chain, audit_file = temp_audit_env
    
    for i in range(1, 11):
        chain.log_event("system", f"action_{i}", "admin", {"data": i})
        
    proof_data = chain.get_audit_proof(5)
    
    # Manipulate a sibling hash in the proof
    manipulated_proof = list(proof_data["proof"])
    manipulated_proof[0] = {
        "position": manipulated_proof[0]["position"],
        "hash": "bad" * 16  # 64 chars
    }
    
    is_valid = MerkleTree.verify_proof(
        proof_data["leaf"],
        manipulated_proof,
        proof_data["root"]
    )
    assert not is_valid, "Failed to detect manipulated sibling hash in proof"

def test_get_audit_proof_empty_chain(temp_audit_env):
    chain, audit_file = temp_audit_env
    
    with pytest.raises(ValueError, match="Audit log empty or missing"):
        chain.get_audit_proof(1)

def test_get_audit_proof_unsealed_event(temp_audit_env):
    chain, audit_file = temp_audit_env
    
    # Log 1 event (doesn't trigger a checkpoint yet)
    chain.log_event("system", "action_1", "admin", {"data": 1})
    
    with pytest.raises(ValueError, match="exists but is pending Merkle checkpoint"):
        chain.get_audit_proof(1)

def test_get_audit_proof_exclusion(temp_audit_env):
    chain, audit_file = temp_audit_env
    
    # Ensure there is a sealed block
    for i in range(1, 11):
        chain.log_event("system", f"action_{i}", "admin", {"data": i})
        
    with pytest.raises(ValueError, match="not found in sealed checkpoints \\(Exclusion\\)"):
        chain.get_audit_proof(999)
