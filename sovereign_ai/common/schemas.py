from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class SigningAlgorithm(str, Enum):
    ED25519 = "ed25519"
    P256 = "p256"      # NIST Curve (TPM Compatible)
    RSA2048 = "rsa2048"
    RSA3072 = "rsa3072"

class RecordStatus(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    CONFIRM = "confirm"
    PASS = "pass"
    FAIL = "fail"
    SUCCESS = "success"
    EXEC_ERROR = "exec_error"
    PENDING = "pending"

class EvidenceType(str, Enum):
    TPM2_QUOTE = "TPM2_QUOTE"
    SGX_REPORT = "SGX_REPORT"
    MOCK_SIM = "MOCK_SIM"

class AttestationQuote(BaseModel):
    """Hardware-signed quote containing PCRs or Enclave measurements."""
    model_config = ConfigDict(frozen=True)

    type: EvidenceType = EvidenceType.TPM2_QUOTE
    quote_data: str = Field(..., description="Base64 encoded TPM2_Quote or SGX_Report")
    pcr_values: Dict[int, str] = Field(..., description="PCR index to hash value mapping")
    firmware_version: str
    runtime_measurement: str = Field(..., description="SHA256 of the running binary/config")
    signature: str = Field(..., description="Digital signature of the quote (AIK/EK)")

class SecurityHalt(Exception):
    """Raised when a security failure (e.g. attestation) requires halting operations."""
    pass
