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


def verify_envelope(envelope: WorkflowEvidenceEnvelope, expected_nonce: str | None = None) -> bool:
    if expected_nonce is not None and envelope.nonce != expected_nonce:
        return False
    if envelope.action != "case_file.update" or not envelope.executed:
        return False
    if envelope.approval_required and not envelope.approved_by:
        return False
    if envelope.input_hash != value_hash(envelope.request.model_dump(mode="json")):
        return False
    if envelope.output_hash != value_hash(envelope.result):
        return False
    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(
            base64.b64decode(envelope.public_key)
        )
        public_key.verify(
            base64.b64decode(envelope.signature),
            canonical_unsigned(envelope.model_dump()),
        )
        return True
    except (ValueError, InvalidSignature):
        return False
