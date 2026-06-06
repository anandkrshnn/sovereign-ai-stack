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
    version="0.1.0a2",
)

# In-memory store for Golden References (Reference Values)
# In production, this would be a secure database or signed manifest.
# Values are aligned with sovereign_ai.common.hardware_trust.mock_sim defaults for preview.
GOLDEN_REFERENCES = {
    "v0.1.0a2": {
        "app_hash": hashlib.sha256(b"simulated_runtime_state").hexdigest(),
        "pcr0": "tpm2_pcr0_bios_hash",
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


# Lazy-loaded verifier components
_policy_verifier = None
_nli_evaluator = None


def get_policy_verifier():
    global _policy_verifier
    if _policy_verifier is None:
        from sovereign_ai.verify.policy_z3 import PolicyVerifier

        _policy_verifier = PolicyVerifier()
    return _policy_verifier


def get_nli_evaluator():
    global _nli_evaluator
    if _nli_evaluator is None:
        from sovereign_ai.verify.evaluator import SovereignEvaluator

        _nli_evaluator = SovereignEvaluator()
    return _nli_evaluator


class PolicyVerificationRequest(BaseModel):
    principal: str
    resource: str
    action: str
    policies: List[Dict[str, Any]]
    check_type: str = "authorize"  # "authorize", "reachability", "conflicts"


class PolicyVerificationResponse(BaseModel):
    is_authorized: bool = False
    is_reachable: Optional[bool] = None
    conflicts: Optional[List[str]] = None


class NLIVerificationRequest(BaseModel):
    query: str
    context: str
    answer: str


class NLIVerificationResponse(BaseModel):
    grounding_score: float
    faithfulness_score: float
    overall_score: float
    passed: bool
    raw_scores: Optional[List[float]] = None


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
        raise HTTPException(
            status_code=400, detail=f"Unknown reference version: {request.reference_version}"
        )

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
        evidence_type=request.bundle.quote.type if request.bundle.quote else EvidenceType.MOCK_SIM,
    )


@app.post("/verify/policy", response_model=PolicyVerificationResponse)
def verify_policy(request: PolicyVerificationRequest, api_key: str = Depends(verify_api_key)):
    """
    Performs formal ABAC SMT verification inside the isolated service.
    """
    verifier = get_policy_verifier()

    is_auth = False
    is_reach = None
    conflicts = None

    if request.check_type == "authorize":
        is_auth = verifier.is_authorized(
            request.principal, request.resource, request.action, request.policies
        )
    elif request.check_type == "reachability":
        is_reach = verifier.check_reachability(
            request.principal, request.resource, request.policies
        )
    elif request.check_type == "conflicts":
        conflicts = verifier.detect_conflicts(request.policies)

    return PolicyVerificationResponse(
        is_authorized=is_auth, is_reachable=is_reach, conflicts=conflicts
    )


@app.post("/verify/nli", response_model=NLIVerificationResponse)
def verify_nli(request: NLIVerificationRequest, api_key: str = Depends(verify_api_key)):
    """
    Performs Cross-Encoder NLI grounding checks inside the isolated service.
    """
    evaluator = get_nli_evaluator()
    res = evaluator.evaluate(request.query, request.context, request.answer)
    return NLIVerificationResponse(
        grounding_score=res["grounding_score"],
        faithfulness_score=res["faithfulness_score"],
        overall_score=res["overall_score"],
        passed=res["passed"],
        raw_scores=res.get("raw_scores"),
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
