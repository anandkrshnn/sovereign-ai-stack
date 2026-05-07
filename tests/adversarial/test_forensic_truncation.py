import os
import pytest
from pathlib import Path
from sovereign_ai.common.audit import SignedAuditChain, SecurityHalt
from sovereign_ai.common.hardware_trust import SoftwareSimulatorAnchor

def test_audit_truncation_detection():
    """
    Adversarial Test: Verify that the system detects log truncation via the checkpoint file.
    """
    audit_file = Path("tests/adversarial/truncation_audit.jsonl")
    checkpoint_file = audit_file.with_suffix(".checkpoint")
    
    # Cleanup
    if audit_file.exists(): audit_file.unlink()
    if checkpoint_file.exists(): checkpoint_file.unlink()
    
    anchor = SoftwareSimulatorAnchor(tenant_id="truncation_test")
    chain = SignedAuditChain(tenant_id="test", audit_file=str(audit_file), anchor=anchor)
    
    # 1. Generate a valid chain with 5 records
    for i in range(5):
        chain.log_event("test", f"action_{i}", "user", {"data": i})
    
    assert audit_file.exists()
    assert checkpoint_file.exists()
    
    # Verify valid chain
    assert chain.verify_chain() is True
    
    # 2. Simulate truncation (attacker deletes the last 2 records)
    with open(audit_file, "r") as f:
        lines = f.readlines()
    
    truncated_lines = lines[:-2]
    with open(audit_file, "w") as f:
        f.writelines(truncated_lines)
        
    # 3. Instantiate a NEW chain object (simulating a system restart/verification)
    # The new object should detect that the file is shorter than the checkpoint record
    try:
        new_chain = SignedAuditChain(tenant_id="test", audit_file=str(audit_file), anchor=anchor)
        # If it doesn't raise on init, try verify
        is_valid = new_chain.verify_chain()
        assert is_valid is False, "Truncation was NOT detected during verification!"
    except SecurityHalt:
        print("SUCCESS: Truncation detected via SecurityHalt on initialization.")
    except Exception as e:
        pytest.fail(f"Unexpected exception: {e}")
    print("SUCCESS: Truncation detected via checkpoint verification.")

if __name__ == "__main__":
    test_audit_truncation_detection()
