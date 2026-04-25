from sovereign_ai.common.audit import SovereignAuditLogger, Principal
import os

def test_audit_generation():
    print("Running Test 2: Verify Unified Audit Chain...")
    
    base_dir = "data"
    tenant_id = "test_tenant"
    logger = SovereignAuditLogger(base_dir, tenant_id)
    
    p = Principal(id="dr_smith", tenant_id=tenant_id)
    
    # Log some events
    print("Logging events to chain...")
    logger.log("request_start", p, {"query": "Hello"})
    logger.log("rag_retrieval", p, {"chunks": 5})
    logger.log("verification_passed", p, {"score": 0.95})
    
    # Verify integrity
    print("Verifying chain integrity...")
    if logger.verify_integrity():
        print("Unified Audit Chain Verified: 100% Integrity.")
    else:
        print("Audit Chain Verification Failed.")
        raise Exception("Integrity failure!")

if __name__ == "__main__":
    test_audit_generation()
