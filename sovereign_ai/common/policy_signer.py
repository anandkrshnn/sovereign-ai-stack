import yaml
import hashlib
import base64
from pathlib import Path
from typing import Optional
from .hardware_trust import SecureAnchor, SoftwareSimulatorAnchor, WindowsTPMAnchor

class PolicySigner:
    """
    Utility to sign Sovereign ABAC policies for integrity verification.
    """
    def __init__(self, anchor: SecureAnchor):
        self.anchor = anchor

    def sign_policy(self, policy_path: str) -> str:
        """
        Signs a policy file and creates a .sig file.
        Returns the path to the signature file.
        """
        path = Path(policy_path)
        if not path.exists():
            raise FileNotFoundError(f"Policy file not found: {policy_path}")

        # Read binary content to ensure stable signature regardless of platform newlines
        with open(path, "rb") as f:
            content = f.read()
        
        # We sign the raw bytes of the file content
        signature = self.anchor.sign(content)
        
        # We store the signature as base64 in a separate file
        sig_path = path.with_suffix(path.suffix + ".sig")
        with open(sig_path, "w", encoding="utf-8") as f:
            f.write(base64.b64encode(signature).decode("utf-8"))
        
        return str(sig_path)

if __name__ == "__main__":
    import argparse
    import os
    from cryptography.hazmat.primitives import serialization

    parser = argparse.ArgumentParser(description="Sovereign AI Policy Signer")
    parser.add_argument("policy", help="Path to policy.yaml")
    parser.add_argument("--key", help="Path to Ed25519 private key (optional, uses simulator if missing)")
    parser.add_argument("--tpm", action="store_true", help="Use Windows TPM for signing")
    
    args = parser.parse_args()
    
    if args.tpm:
        print("Using Windows TPM Anchor...")
        anchor = WindowsTPMAnchor(tenant_id="admin", key_name="policy_root")
    elif args.key and os.path.exists(args.key):
        print(f"Using Private Key: {args.key}")
        from cryptography.hazmat.primitives.asymmetric import ed25519
        with open(args.key, "rb") as f:
            key = ed25519.Ed25519PrivateKey.from_private_bytes(f.read()[-32:])
        anchor = SoftwareSimulatorAnchor(private_key=key)
    else:
        print("Using ephemeral SoftwareSimulatorAnchor (WARNING: For development only!)")
        anchor = SoftwareSimulatorAnchor()

    signer = PolicySigner(anchor)
    try:
        sig_file = signer.sign_policy(args.policy)
        print(f"Successfully signed policy: {args.policy}")
        print(f"Signature stored at: {sig_file}")
        
        # Output the public key for the PolicyEngine config
        pub_key = anchor.get_public_key()
        if hasattr(pub_key, "public_bytes"):
            pub_bytes = pub_key.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw
            )
            print(f"Root of Trust (Public Key B64): {base64.b64encode(pub_bytes).decode('utf-8')}")
    except Exception as e:
        print(f"Error: {e}")
