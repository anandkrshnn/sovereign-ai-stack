"""Tamil Nadu e-Sevai case-file update vertical slice."""

from __future__ import annotations

import base64
from typing import Any
from uuid import UUID, uuid4

from cryptography.hazmat.primitives import serialization

from evidence_envelope import (
    CaseFileUpdate,
    WorkflowEvidenceEnvelope,
    canonical_unsigned,
    value_hash,
    verify_envelope,
)

from ..common.hardware_trust import SecureAnchor


def _public_key_bytes(anchor: SecureAnchor) -> bytes:
    key = anchor.get_public_key()
    if anchor.algorithm.value == "ed25519":
        return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return anchor.get_public_key_pem()


class TamilNaduWorkflow:
    """One deterministic propose -> policy -> approval -> execute -> sign path."""

    def __init__(self, anchor: SecureAnchor, webhook: Any | None = None):
        self.anchor = anchor
        self.webhook = webhook
        self._pending: dict[str, WorkflowEvidenceEnvelope] = {}

    def propose(self, request: CaseFileUpdate) -> dict[str, Any]:
        return {"action": "case_file.update", "request": request.model_dump(mode="json")}

    def opa_decide(self, request: CaseFileUpdate) -> dict[str, Any]:
        """Return the OPA-compatible decision shape used by the trust plane."""

        if request.field == "document_reference" and request.value.lower().startswith("delete"):
            return {
                "allow": False,
                "approval_required": False,
                "reason": "destructive_update_denied",
            }
        if request.entity_id != "citizen-42":
            return {"allow": False, "approval_required": False, "reason": "entity_mismatch"}
        if request.amount_inr is not None:
            return {
                "allow": False,
                "approval_required": False,
                "reason": "numeric_field_not_supported",
            }
        return {
            "allow": True,
            "approval_required": True,
            "reason": "regulated_case_file_write_requires_operator",
        }

    def submit(self, request: CaseFileUpdate) -> WorkflowEvidenceEnvelope:
        decision = self.opa_decide(request)
        run_id = uuid4()
        import secrets

        nonce = secrets.token_hex(32)
        result: dict[str, Any] = {}
        envelope = self._build(
            run_id, request, decision, executed=False, result=result, nonce=nonce, approved_by=None
        )
        if decision["allow"] and decision["approval_required"]:
            self._pending[str(run_id)] = envelope
        return envelope

    def approve_and_execute(self, run_id: UUID, principal: str) -> WorkflowEvidenceEnvelope:
        pending = self._pending.pop(str(run_id))
        request = pending.request
        decision = self.opa_decide(request)
        if not decision["allow"]:
            return pending
        result = self._execute_webhook(request)
        return self._build(
            run_id,
            request,
            decision,
            executed=result.get("status") != "blocked",
            result=result,
            nonce=pending.nonce,
            approved_by=principal,
        )

    def _execute_webhook(self, request: CaseFileUpdate) -> dict[str, Any]:
        if self.webhook is None:
            return {"status": "simulated", "case_id": request.case_id, "updated": request.field}
        for attempt in range(1, 3):
            try:
                return dict(self.webhook(request.model_dump(mode="json"), timeout_seconds=30))
            except TimeoutError:
                if attempt == 2:
                    return {"status": "blocked", "error": "webhook_timeout", "attempts": attempt}
        raise RuntimeError("unreachable")

    def _build(
        self,
        run_id: UUID,
        request: CaseFileUpdate,
        decision: dict[str, Any],
        executed: bool,
        result: dict[str, Any],
        nonce: str,
        approved_by: str | None,
    ) -> WorkflowEvidenceEnvelope:
        payload = {
            "run_id": run_id,
            "action": "case_file.update",
            "request": request.model_dump(mode="json"),
            "policy_allowed": decision["allow"],
            "approval_required": decision["approval_required"],
            "approved_by": approved_by,
            "executed": executed,
            "result": result,
            "input_hash": value_hash(request.model_dump(mode="json")),
            "output_hash": value_hash(result),
            "nonce": nonce,
            "public_key": base64.b64encode(_public_key_bytes(self.anchor)).decode(),
        }
        unsigned = WorkflowEvidenceEnvelope(**payload, signature="")
        signature = base64.b64encode(
            self.anchor.sign(canonical_unsigned(unsigned.model_dump()))
        ).decode()
        return unsigned.model_copy(update={"signature": signature})


__all__ = ["CaseFileUpdate", "TamilNaduWorkflow", "WorkflowEvidenceEnvelope", "verify_envelope"]
