import json
import hashlib
from pathlib import Path
from sovereign_ai.common.audit import SignedAuditChain
from sovereign_ai.common.hardware_trust import SoftwareSimulatorAnchor, LegacyRawAnchor, WindowsTPMAnchor

def demonstrate_genesis_link():
    """
    Demonstrate the Genesis Transition Block protocol.
    Linking a legacy Ed25519 chain to a new P-256 (TPM) chain.
    """
    legacy_file = Path("data/audit_v1_ed25519.jsonl")
    new_file = Path("data/audit_v2_p256.jsonl")
    
    # Clean state
    for f in [legacy_file, new_file]:
        if f.exists(): f.unlink()
        checkpoint = f.with_suffix(".checkpoint")
        if checkpoint.exists(): checkpoint.unlink()
    
    # Setup legacy chain (Ed25519)
    from cryptography.hazmat.primitives.asymmetric import ed25519
    legacy_anchor = LegacyRawAnchor(ed25519.Ed25519PrivateKey.generate())
    legacy_chain = SignedAuditChain(tenant_id="demo", audit_file=str(legacy_file), anchor=legacy_anchor)
    legacy_chain.log_event("system", "LOG_LEGACY", "admin", {"msg": "Ending Ed25519 era"})
    
    final_legacy_hash = legacy_chain.last_hash
    print(f"Final Legacy Hash: {final_legacy_hash}")
    
    # Transition: Start NEW P-256 chain with a GENESIS_TRANSITION block
    new_anchor = WindowsTPMAnchor(tenant_id="demo") # Simulating/Using TPM P-256
    new_chain = SignedAuditChain(tenant_id="demo", audit_file=str(new_file), anchor=new_anchor)
    
    # The GENESIS_TRANSITION block contains the last hash of the previous chain
    new_chain.log_event(
        component="security",
        action="GENESIS_TRANSITION",
        principal="system",
        event_data={
            "transition": "Ed25519 -> P-256",
            "prev_chain_file": str(legacy_file),
            "prev_chain_final_hash": final_legacy_hash,
            "policy_version": "1.1.0"
        }
    )
    
    print(f"Genesis Block Hash: {new_chain.last_hash}")
    print(f"New chain started with algorithm: {new_chain.pinned_algorithm}")
    
    # Verify both
    assert legacy_chain.verify_chain()
    assert new_chain.verify_chain()
    
    print("\nSUCCESS: Genesis Link established. Forensic continuity preserved across algorithms.")

if __name__ == "__main__":
    demonstrate_genesis_link()
