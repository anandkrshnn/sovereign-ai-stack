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
        Deep validation for native TPM 2.0 quotes.
        """
        quote = bundle.quote
        
        # Structural Validation: In real TPM, quote_data is the TPM2B_ATTEST blob
        # For Phase 3, we check for structural indicators or placeholders
        if quote.quote_data and len(quote.quote_data) > 0:
            results["checks"]["structure_valid"] = True
        else:
            results["errors"].append("Invalid TPM quote structure: Missing TPM2B_ATTEST.")

        # Measurement Validation
        if quote.runtime_measurement == self.reference_values.get("app_hash"):
            results["checks"]["measurements_valid"] = True
        else:
            results["errors"].append(f"TPM PCR Measurement mismatch. Got: {quote.runtime_measurement}")

        # Signature Validation (Simulated)
        # TODO: Implement real RSA/ECDSA signature verification using AIK Cert
        if quote.signature:
            results["checks"]["signature_valid"] = True
        else:
            results["errors"].append("TPM quote signature missing.")

    def _verify_mock_quote(self, bundle: EvidenceBundle, results: Dict[str, Any]):
        """
        Validation logic for simulator-based evidence.
        """
        quote = bundle.quote
        results["checks"]["structure_valid"] = True # Simulator is always 'structurally valid'
        
        if quote.runtime_measurement == self.reference_values.get("app_hash"):
            results["checks"]["measurements_valid"] = True
        else:
            results["errors"].append(f"Simulator measurement mismatch.")

        results["checks"]["signature_valid"] = True # Simulator signatures are auto-trusted in dev

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
