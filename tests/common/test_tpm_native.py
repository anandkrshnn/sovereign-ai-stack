import pytest
import os
import shutil
from sovereign_ai.common.hardware_trust import WindowsTPMAnchor
from sovereign_ai.common.schemas import SigningAlgorithm

@pytest.mark.skipif(os.name != 'nt', reason="Native TPM tests only run on Windows")
def test_windows_tpm_anchor_real():
    """Verify that the native Windows TPM anchor works as expected."""
    tenant_id = "test_native_tpm"
    anchor = WindowsTPMAnchor(tenant_id=tenant_id)
    
    status = anchor.get_status()
    print(f"\nTPM Status: {status}")
    
    # Sign data
    data = b"Forensic integrity check"
    signature = anchor.sign(data)
    assert len(signature) > 0
    
    # Get public key and verify
    pub_key = anchor.get_public_key()
    
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec, rsa, padding
    
    # This will raise an exception if verification fails
    if anchor.algorithm == SigningAlgorithm.RSA2048:
        pub_key.verify(
            signature,
            data,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
    else:
        pub_key.verify(signature, data, ec.ECDSA(hashes.SHA256()))
    
    print("Verification successful!")

if __name__ == "__main__":
    test_windows_tpm_anchor_real()
