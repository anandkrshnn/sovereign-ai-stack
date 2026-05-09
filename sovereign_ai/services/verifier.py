from fastapi import FastAPI, HTTPException, Depends, Header
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
import hashlib
import uvicorn

from sovereign_ai.common.rats import EvidenceBundle, AttestationVerifier
from sovereign_ai.common.schemas import EvidenceType
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verifier")

# Simple API Key for Phase 2 Preview
VERIFIER_API_KEY = os.getenv("VERIFIER_API_KEY", "sovereign_trust_preview_2026")

app = FastAPI(
    title="Sovereign AI Attestation Verifier",
    description="IETF RATS-aligned verification service for forensic audit evidence.",
    version="0.1.0a2"
)

# In-memory store for Golden References (Reference Values)
# In production, this would be a secure database or signed manifest.
# Values are aligned with sovereign_ai.common.hardware_trust.mock_sim defaults for preview.
GOLDEN_REFERENCES = {
    "v0.1.0a2": {
        "app_hash": hashlib.sha256(b"simulated_runtime_state").hexdigest(),
        "pcr0": "tpm2_pcr0_bios_hash"
    }
}

class VerificationRequest(BaseModel):
    bundle: EvidenceBundle
    expected_nonce: str
    reference_version: str = "v0.1.0a2"

class VerificationResponse(BaseModel):
    is_valid: bool
    verified_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    checks: Dict[str, bool]
    errors: List[str]
    evidence_type: EvidenceType

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != VERIFIER_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid Verifier API Key")
    return x_api_key

@app.get("/health")
def health_check():
    return {"status": "operational", "timestamp": datetime.now(timezone.utc)}

@app.get("/reference-values")
def get_references(api_key: str = Depends(verify_api_key)):
    """List available golden reference sets."""
    return GOLDEN_REFERENCES

@app.post("/verify", response_model=VerificationResponse)
def verify_attestation(request: VerificationRequest, api_key: str = Depends(verify_api_key)):
    """
    Validates an EvidenceBundle against a specific Reference Version.
    Implements IETF RATS verification lifecycle.
    """
    logger.info(f"Received attestation request for version {request.reference_version}")
    
    if request.reference_version not in GOLDEN_REFERENCES:
        logger.warning(f"Unknown reference version: {request.reference_version}")
        raise HTTPException(status_code=400, detail=f"Unknown reference version: {request.reference_version}")
    
    ref_values = GOLDEN_REFERENCES[request.reference_version]
    verifier = AttestationVerifier(ref_values)
    
    # Execute formal verification
    results = verifier.verify_bundle(request.bundle, request.expected_nonce)
    
    if results["is_valid"]:
        logger.info("Verification SUCCESSful")
    else:
        logger.error(f"Verification FAILED: {results['errors']}")
    
    return VerificationResponse(
        is_valid=results["is_valid"],
        checks=results["checks"],
        errors=results["errors"],
        evidence_type=request.bundle.quote.type if request.bundle.quote else EvidenceType.MOCK_SIM
    )

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
