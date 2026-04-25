from sovereign_ai.common.identity import IdentityHub
from sovereign_ai.common.audit import Principal

def run_identity_test():
    print("Running Test 3: Verify Identity Sync...")
    
    hub = IdentityHub()
    
    # Resolve a principal
    p = hub.resolve_mock("doctor", tenant_id="hosp_001")
    
    print(f"Principal ID: {p.id}")
    print(f"Tenant ID:    {p.tenant_id}")
    print(f"Roles:        {p.roles}")
    print(f"Classifications: {p.classifications}")
    
    # Verify attributes
    assert p.id == "dr_smith"
    assert p.tenant_id == "hosp_001"
    assert "doctor" in p.roles
    assert "confidential" in p.classifications
    
    # Test dictionary conversion (for auditing)
    p_dict = p.to_dict()
    assert p_dict["id"] == "dr_smith"
    
    print("Test 3 PASSED: Identity correctly resolved and synced.")

if __name__ == "__main__":
    run_identity_test()
