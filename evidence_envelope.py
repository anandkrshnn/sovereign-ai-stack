"""Standalone Tamil Nadu case-file evidence schema and verifier.

This module has no dependency on the application runner, policy, adapters, or
hardware abstraction. It is intentionally usable by an independent verifier.
"""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Collection, Mapping
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from pydantic import BaseModel, ConfigDict, Field


class CaseFileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case_id: str = Field(min_length=1, max_length=100)
    field: str = Field(pattern=r"^(status|address|document_reference)$")
    value: str = Field(min_length=1, max_length=500)
    entity_id: str = Field(min_length=1, max_length=100)
    amount_inr: int | None = Field(default=None, ge=0, le=10_000_000)


class WorkflowEvidenceEnvelope(BaseModel):
    schema_version: Literal["tn-seva.case-file.v2"] = "tn-seva.case-file.v2"
    tenant_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    run_id: UUID
    action: str
    request: CaseFileUpdate
    policy_allowed: bool
    approval_required: bool
    approved_by: str | None = None
    executed: bool | None
    result: dict[str, Any] = Field(default_factory=dict)
    input_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    approval_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    nonce: str = Field(min_length=32)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    public_key: str
    signature: str

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


def canonical_unsigned(payload: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in payload.items() if key != "signature"}
    return json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
    ).encode()


def value_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False
        ).encode()
    ).hexdigest()


def request_digest(
    tenant_id: str, run_id: UUID, nonce: str, request: CaseFileUpdate, policy_version: str
) -> str:
    """Bind the exact regulated action and authorization scope, not just its text."""
    return value_hash(
        {
            "tenant_id": tenant_id,
            "run_id": str(run_id),
            "nonce": nonce,
            "action": "case_file.update",
            "consequence": "write",
            "request": request.model_dump(mode="json"),
            "policy_version": policy_version,
        }
    )


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
    def executed(self) -> bool | None:
        value = self.get("executed")
        return None if value is None else bool(value)

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
    envelope: WorkflowEvidenceEnvelope,
    expected_nonce: str | None = None,
    *,
    trusted_signers: Mapping[str, Collection[str]] | None = None,
    expected_tenant_id: str | None = None,
) -> VerificationResult:
    """Verify against an OUT-OF-BAND tenant registry; bundled keys never establish trust."""

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
    if envelope.schema_version != "tn-seva.case-file.v2":
        return _invalid()
    if expected_tenant_id is not None and envelope.tenant_id != expected_tenant_id:
        return _invalid()
    registered = (trusted_signers or {}).get(envelope.tenant_id, ())
    if isinstance(registered, str) or envelope.public_key not in registered:
        return _invalid()
    if expected_nonce is not None and envelope.nonce != expected_nonce:
        return _invalid()
    if envelope.input_hash != value_hash(envelope.request.model_dump(mode="json")):
        return _invalid()
    if envelope.output_hash != value_hash(envelope.result):
        return _invalid()
    expected_digest = request_digest(
        envelope.tenant_id,
        envelope.run_id,
        envelope.nonce,
        envelope.request,
        envelope.policy_version,
    )
    if envelope.request_digest != expected_digest:
        return _invalid()
    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(
            base64.b64decode(envelope.public_key, validate=True)
        )
        public_key.verify(
            base64.b64decode(envelope.signature, validate=True),
            canonical_unsigned(envelope.model_dump()),
        )
    except (ValueError, InvalidSignature, TypeError):
        return _invalid()

    if (
        not envelope.policy_allowed
        and envelope.executed is False
        and envelope.approved_by is None
        and envelope.approval_digest is None
    ):
        return VerificationResult(
            valid=True,
            decision="denied",
            run_id=str(envelope.run_id),
            executed=envelope.executed,
            policy_allowed=envelope.policy_allowed,
        )

    if not envelope.policy_allowed or not envelope.approval_required:
        return _invalid()
    if (
        envelope.executed is False
        and envelope.approved_by is None
        and envelope.approval_digest is None
        and not envelope.result
    ):
        return VerificationResult(
            valid=True,
            decision="pending",
            run_id=str(envelope.run_id),
            executed=False,
            policy_allowed=True,
        )
    if (
        not envelope.approved_by
        or not envelope.approved_by.strip()
        or envelope.approval_digest != expected_digest
    ):
        return _invalid()
    if envelope.executed is True:
        status = envelope.result.get("status")
        if status not in {"completed", "simulated"}:
            return _invalid()
        if status == "completed":
            receipt = envelope.result.get("receipt_id")
            if not isinstance(receipt, str) or not receipt.strip():
                return _invalid()
        return VerificationResult(
            valid=True,
            decision="allowed",
            run_id=str(envelope.run_id),
            executed=envelope.executed,
            policy_allowed=envelope.policy_allowed,
        )

    if (
        envelope.policy_allowed
        and envelope.executed is False
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

    if envelope.executed is None and envelope.result.get("status") == "unknown":
        return VerificationResult(
            valid=True,
            decision="unknown",
            run_id=str(envelope.run_id),
            executed=None,
            policy_allowed=True,
        )
    return _invalid()
