"""Standalone Tamil Nadu case-file evidence schema and verifier.

This module has no dependency on the application runner, policy, adapters, or
hardware abstraction. It is intentionally usable by an independent verifier.
"""

from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic import BaseModel, ConfigDict, Field


class CaseFileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(min_length=1, max_length=100)
    field: str = Field(pattern=r"^(status|address|document_reference)$")
    value: str = Field(min_length=1, max_length=500)
    entity_id: str = Field(min_length=1, max_length=100)
    amount_inr: int | None = Field(default=None, ge=0, le=10_000_000)


class WorkflowEvidenceEnvelope(BaseModel):
    schema_version: str = "tn-seva.case-file.v1"
    run_id: UUID
    action: str
    request: CaseFileUpdate
    policy_allowed: bool
    approval_required: bool
    approved_by: str | None = None
    executed: bool
    result: dict[str, Any] = Field(default_factory=dict)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    nonce: str = Field(min_length=32)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    public_key: str
    signature: str

    model_config = ConfigDict(extra="forbid")


def canonical_unsigned(payload: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in payload.items() if key != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), default=str).encode()


def value_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


class VerificationResult(dict):
    @property
    def valid(self) -> bool:
        return bool(self.get("valid", False))

    @property
    def decision(self) -> str:
        return str(self.get("decision", "invalid"))

    @property
    def run_id(self) -> str:
        return str(self.get("run_id", ""))

    @property
    def executed(self) -> bool:
        return bool(self.get("executed", False))

    @property
    def policy_allowed(self) -> bool:
        return bool(self.get("policy_allowed", False))

    def __bool__(self) -> bool:
        return self.valid

    def __eq__(self, other: object) -> bool:
        if isinstance(other, bool):
            return self.valid is other
        return super().__eq__(other)


def verify_envelope(
    envelope: WorkflowEvidenceEnvelope, expected_nonce: str | None = None
) -> VerificationResult:
    def _invalid() -> VerificationResult:
        return VerificationResult(
            valid=False,
            decision="invalid",
            run_id=str(envelope.run_id),
            executed=envelope.executed,
            policy_allowed=envelope.policy_allowed,
        )

    if envelope.action != "case_file.update":
        return _invalid()
    if expected_nonce is not None and envelope.nonce != expected_nonce:
        return _invalid()
    if envelope.approval_required and envelope.executed and not envelope.approved_by:
        return _invalid()
    if envelope.input_hash != value_hash(envelope.request.model_dump(mode="json")):
        return _invalid()
    if envelope.output_hash != value_hash(envelope.result):
        return _invalid()
    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(
            base64.b64decode(envelope.public_key)
        )
        public_key.verify(
            base64.b64decode(envelope.signature),
            canonical_unsigned(envelope.model_dump()),
        )
    except (ValueError, InvalidSignature, TypeError):
        return _invalid()

    if not envelope.policy_allowed and not envelope.executed:
        return VerificationResult(
            valid=True,
            decision="denied",
            run_id=str(envelope.run_id),
            executed=envelope.executed,
            policy_allowed=envelope.policy_allowed,
        )

    if envelope.policy_allowed and envelope.executed:
        return VerificationResult(
            valid=True,
            decision="allowed",
            run_id=str(envelope.run_id),
            executed=envelope.executed,
            policy_allowed=envelope.policy_allowed,
        )

    if (
        envelope.policy_allowed
        and not envelope.executed
        and envelope.result.get("status") == "blocked"
        and (not envelope.approval_required or envelope.approved_by)
    ):
        return VerificationResult(
            valid=True,
            decision="blocked",
            run_id=str(envelope.run_id),
            executed=envelope.executed,
            policy_allowed=envelope.policy_allowed,
        )

    return _invalid()
