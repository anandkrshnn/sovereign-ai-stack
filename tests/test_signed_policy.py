import os
import yaml
import base64
import pytest
from pathlib import Path
from sovereign_ai.rag.policy import PolicyEngine, AccessRequest
from sovereign_ai.common.policy_signer import PolicySigner
from sovereign_ai.common.hardware_trust import SoftwareSimulatorAnchor
from sovereign_ai.common.audit import Principal
from sovereign_ai.rag.schemas import SearchResult
from cryptography.hazmat.primitives import serialization

def test_signed_policy_lifecycle(tmp_path):
    # 1. Setup
    policy_file = tmp_path / "test_policy.yaml"
    policy_content = {
        "version": "1.0.0",
        "allow": [{"roles": ["admin"], "classifications": ["secret"]}],
        "deny": []
    }
    with open(policy_file, "w") as f:
        yaml.dump(policy_content, f)

    anchor = SoftwareSimulatorAnchor(tenant_id="admin")
    signer = PolicySigner(anchor)
    pub_key = anchor.get_public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw
    )
    pub_b64 = base64.b64encode(pub_key).decode()

    # 2. Sign Policy
    sig_file = signer.sign_policy(str(policy_file))
    assert os.path.exists(sig_file)

    # 3. Load with verification (Success)
    engine = PolicyEngine(policy_path=str(policy_file), trusted_public_key=pub_b64, strict_mode=True)
    assert engine.verify_signature() is True
    assert engine.policy["version"] == "1.0.0"

    # 4. Tamper with policy
    with open(policy_file, "a") as f:
        f.write("\n# tampered")
    
    # Reload engine (Failure)
    engine_tampered = PolicyEngine(policy_path=str(policy_file), trusted_public_key=pub_b64, strict_mode=True)
    # In strict mode, it should default to Deny-All if verification fails
    assert engine_tampered.policy["deny"][0]["classification"] == "all"
    
    # 5. Missing signature
    os.remove(sig_file)
    engine_missing = PolicyEngine(policy_path=str(policy_file), trusted_public_key=pub_b64, strict_mode=True)
    assert engine_missing.policy["deny"][0]["classification"] == "all"

if __name__ == "__main__":
    # Run test manually if called directly
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as tmp:
        test_signed_policy_lifecycle(Path(tmp))
        print("Signed Policy Lifecycle Test: PASSED")
