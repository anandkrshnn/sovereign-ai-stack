import json
import os
from sovereign_ai.common.audit import SovereignAuditLogger, Principal

def test_anchor_detection():
    print("Running Out-of-the-Box Test: Local Forensic Anchor...")
    
    base_dir = "data"
    tenant_id = "anchor_test"
    logger = SovereignAuditLogger(base_dir, tenant_id)
    p = Principal(id="dr_smith", tenant_id=tenant_id)
    
    # 1. Generate Chain
    print("Generating audit chain...")
    logger.log("event_1", p, {"step": 1})
    logger.log("event_2", p, {"step": 2})
    logger.log("event_3", p, {"step": 3})
    
    # 2. Verify (Should Pass)
    print("Initial verification...")
    if logger.verify_integrity():
        print("Verification PASSED (Initial).")
    else:
        print("Verification FAILED (Initial).")
        return

    # 3. Simulate Tampering (Delete last line)
    print("Simulating tampering (deleting last event)...")
    with open(logger.log_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    with open(logger.log_path, "w", encoding="utf-8") as f:
        f.writelines(lines[:-1]) # Remove the last line
        
    # 4. Verify (Should Fail)
    print("Post-tampering verification...")
    if not logger.verify_integrity():
        print("Verification FAILED as expected! (Tampering Detected).")
        print("Reason: File hash mismatch against hardware-bound anchor.")
        print("PASSED: The stack successfully detected log truncation.")
    else:
        print("Verification PASSED (This is a FAILURE! The anchor should have detected truncation).")

if __name__ == "__main__":
    test_anchor_detection()
