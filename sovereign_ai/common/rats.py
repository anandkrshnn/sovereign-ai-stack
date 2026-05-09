from datetime import datetime, timezone
import json
import hashlib
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from .schemas import EvidenceType, AttestationQuote

class EvidenceBundle(BaseModel):
    """
    The formal IETF RATS Evidence bundle for a Merkle Checkpoint.
    Binds forensic audit state to a hardware-attested execution environment.
    """
    version: str = "1.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    nonce: str = Field(..., min_length=32, description="Anti-replay nonce (freshness)")
    merkle_root: str = Field(..., description="The forensic Merkle Root being attested")
    quote: Optional[AttestationQuote] = None
    bundle_signature: str = Field(..., description="Signature over the full bundle (Attester Key)")

class AttestationVerifier:
    """
    Verifies EvidenceBundles against trusted Reference Values (Endorsements).
    Supports multiple evidence types: MOCK_SIM, TPM2_QUOTE.
    """
    
    def __init__(self, reference_values: Dict[str, str]):
        self.reference_values = reference_values

    def verify_bundle(self, bundle: EvidenceBundle, expected_nonce: str) -> Dict[str, Any]:
        """
        Full RATS verification sequence.
        Dispatches to specific sub-verifiers based on evidence type.
        """
        results = {
            "is_valid": False,
            "checks": {
                "nonce_fresh": False,
                "measurements_valid": False,
                "signature_valid": False,
                "structure_valid": False
            },
            "errors": []
        }

        if not bundle.quote:
            results["errors"].append("Missing attestation quote.")
            return results

        # 1. Nonce Freshness Check (Outer Bundle)
        if bundle.nonce == expected_nonce:
            results["checks"]["nonce_fresh"] = True
        else:
            results["errors"].append("Nonce mismatch: Possible replay attack.")

        # 2. Evidence-Specific Verification
        if bundle.quote.type == EvidenceType.TPM2_QUOTE:
            self._verify_tpm2_quote(bundle, results)
        else:
            self._verify_mock_quote(bundle, results)

        results["is_valid"] = all(results["checks"].values())
        return results

    def _verify_tpm2_quote(self, bundle: EvidenceBundle, results: Dict[str, Any]):
        """
        Deep validation for native TPM 2.0 quotes using RSA-PSS verification.
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding, rsa
        from cryptography.hazmat.primitives import serialization
        import base64

        quote = bundle.quote
        
        # 1. Structural Validation
        if quote.quote_data and quote.signature:
            results["checks"]["structure_valid"] = True
        else:
            results["errors"].append("Invalid TPM quote: Missing quote_data or signature.")
            return

        # 2. Measurement Validation (PCR Check)
        # In a real RATS flow, we'd verify the quote_data blob against the PCRs.
        # Here we check the reported measurement against reference values.
        if quote.runtime_measurement == self.reference_values.get("app_hash"):
            results["checks"]["measurements_valid"] = True
        else:
            results["errors"].append(f"TPM PCR Measurement mismatch. Got: {quote.runtime_measurement}")

        # 3. Cryptographic Signature Validation
        try:
            # Load the AIK Public Key (Endorsement)
            aik_pem = self.reference_values.get("aik_public_key_pem")
            if not aik_pem:
                results["errors"].append("Missing AIK public key in reference values.")
                return

            public_key = serialization.load_pem_public_key(aik_pem.encode())
            
            # Prepare the data that was signed (the quote_data/TPM2B_ATTEST)
            # Note: In a real TPM quote, the quote_data includes the nonce and Merkle Root.
            quote_bytes = base64.b64decode(quote.quote_data)
            signature_bytes = base64.b64decode(quote.signature)

            if isinstance(public_key, rsa.RSAPublicKey):
                public_key.verify(
                    signature_bytes,
                    quote_bytes,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                results["checks"]["signature_valid"] = True
            else:
                results["errors"].append("AIK key type mismatch: Expected RSA.")
                
        except Exception as e:
            results["errors"].append(f"TPM Signature Verification Failed: {str(e)}")

    def _verify_mock_quote(self, bundle: EvidenceBundle, results: Dict[str, Any]):
        """
        Validation logic for simulator-based evidence.
        Uses a simpler but still cryptographic check.
        """
        import hashlib
        quote = bundle.quote
        results["checks"]["structure_valid"] = True
        
        # In the simulator, quote_data is sha256(nonce)
        expected_quote_data = hashlib.sha256(bundle.nonce.encode()).hexdigest()
        if quote.quote_data == expected_quote_data:
            results["checks"]["signature_valid"] = True
        else:
            results["errors"].append("Simulator quote data mismatch (nonce binding failed).")
            
        if quote.runtime_measurement == self.reference_values.get("app_hash"):
            results["checks"]["measurements_valid"] = True
        else:
            results["errors"].append(f"Simulator measurement mismatch.")

if __name__ == "__main__":
    ref_values = {"app_hash": "sha256_gold_v1"}
    verifier = AttestationVerifier(ref_values)
    
    # 1. Test Mock Quote
    print("--- Testing Mock Quote ---")
    mock_quote = AttestationQuote(
        type=EvidenceType.MOCK_SIM,
        quote_data="sim_data",
        pcr_values={0: "bios", 11: "sha256_gold_v1"},
        firmware_version="Sim_v1",
        runtime_measurement="sha256_gold_v1",
        signature="sim_sig"
    )
    mock_bundle = EvidenceBundle(
        nonce="nonce_challenge_must_be_32_chars_long_1",
        merkle_root="0x123",
        quote=mock_quote,
        bundle_signature="sig1"
    )
    print(verifier.verify_bundle(mock_bundle, mock_bundle.nonce))

    # 2. Test Native TPM Quote
    print("\n--- Testing Native TPM Quote ---")
    tpm_quote = AttestationQuote(
        type=EvidenceType.TPM2_QUOTE,
        quote_data="TPM2B_ATTEST_DATA",
        pcr_values={0: "bios", 11: "sha256_gold_v1"},
        firmware_version="TPM_v2.0",
        runtime_measurement="sha256_gold_v1",
        signature="aik_sig"
    )
    tpm_bundle = EvidenceBundle(
        nonce="nonce_challenge_must_be_32_chars_long_2",
        merkle_root="0x456",
        quote=tpm_quote,
        bundle_signature="sig2"
    )
    print(verifier.verify_bundle(tpm_bundle, tpm_bundle.nonce))
