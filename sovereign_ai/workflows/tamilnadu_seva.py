"""Tamil Nadu e-Sevai case-file update vertical slice."""

from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from cryptography.hazmat.primitives import serialization

from evidence_envelope import (
    CaseFileUpdate,
    WorkflowEvidenceEnvelope,
    canonical_unsigned,
    request_digest,
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

    policy_version = "tn-seva.policy.v1"

    def __init__(
        self, anchor: SecureAnchor, webhook: Any | None = None, tenant_id: str = "default"
    ):
        if not tenant_id.strip():
            raise ValueError("A tenant is required")
        if anchor.algorithm.value != "ed25519":
            raise ValueError("The portable envelope currently supports Ed25519 anchors only")
        self.anchor = anchor
        self.webhook = webhook
        self.tenant_id = tenant_id
        self._pending: dict[str, WorkflowEvidenceEnvelope] = {}
        self._pending_digests: dict[str, str] = {}
        self._consumed: set[str] = set()

    @property
    def trusted_signers(self) -> dict[str, tuple[str, ...]]:
        # Derived from the configured anchor, NEVER from a submitted envelope.
        return {self.tenant_id: (base64.b64encode(_public_key_bytes(self.anchor)).decode(),)}

    def propose(self, request: CaseFileUpdate) -> dict[str, Any]:
        return {"action": "case_file.update", "request": request.model_dump(mode="json")}

    def opa_decide(self, request: CaseFileUpdate) -> dict[str, Any]:
        """Deterministic stub returning an OPA-compatible decision shape used by the trust plane."""

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
        request = CaseFileUpdate.model_validate(request.model_dump())
        decision = self.opa_decide(request)
        run_id = uuid4()
        import secrets

        nonce = secrets.token_hex(32)
        result: dict[str, Any] = {}
        envelope = self._build(
            run_id, request, decision, executed=False, result=result, nonce=nonce, approved_by=None
        )
        if decision["allow"] and decision["approval_required"]:
            self.load_pending(envelope)
        return envelope

    def load_pending(self, envelope: WorkflowEvidenceEnvelope) -> None:
        """Rehydrate a signed pending file against the host's configured anchor."""
        pending = self._validate_pending(envelope)
        key = str(pending.run_id)
        if key in self._consumed:
            raise ValueError("This run was already dispatched; reconcile rather than retry")
        digest = value_hash(pending.model_dump(mode="json"))
        if key in self._pending_digests and self._pending_digests[key] != digest:
            raise ValueError("Pending request changed")
        self._pending[key] = pending.model_copy(deep=True)
        self._pending_digests[key] = digest

    def _validate_pending(self, envelope: WorkflowEvidenceEnvelope) -> WorkflowEvidenceEnvelope:
        pending = WorkflowEvidenceEnvelope.model_validate(envelope.model_dump())
        report = verify_envelope(
            pending,
            trusted_signers=self.trusted_signers,
            expected_tenant_id=self.tenant_id,
        )
        if not report.valid or report.decision != "pending":
            raise ValueError("Invalid or untrusted pending evidence")
        if pending.policy_version != self.policy_version:
            raise ValueError("Pending policy version changed")
        now = datetime.now(timezone.utc)
        if pending.created_at.tzinfo is None or not (
            now - timedelta(minutes=5) <= pending.created_at <= now
        ):
            raise ValueError("Pending approval expired or timestamp is invalid")
        return pending

    def approve_and_execute(self, run_id: UUID, principal: str) -> WorkflowEvidenceEnvelope:
        # Principal authentication belongs to the host. A string is not an
        # independently verifiable human signature; reject empty assertions.
        if not principal.strip():
            raise ValueError("An authenticated, nonempty host principal is required")
        key = str(run_id)
        pending = self._validate_pending(self._pending[key])
        if pending.run_id != run_id or self._pending_digests.get(key) != value_hash(
            pending.model_dump(mode="json")
        ):
            raise ValueError("Approval is not bound to the original signed request")
        request = pending.request
        decision = self.opa_decide(request)
        if not decision["allow"] or decision["approval_required"] != pending.approval_required:
            raise ValueError("Policy decision changed")
        del self._pending[key]
        del self._pending_digests[key]
        self._consumed.add(key)  # Reserve before dispatch; exceptions must not reopen a write.
        result = self._execute_webhook(request)
        return self._build(
            run_id,
            request,
            decision,
            executed=(
                None if result.get("status") == "unknown" else result.get("status") != "blocked"
            ),
            result=result,
            nonce=pending.nonce,
            approved_by=principal,
            approval_digest=pending.request_digest,
        )

    def _execute_webhook(self, request: CaseFileUpdate) -> dict[str, Any]:
        if self.webhook is None:
            return {"status": "simulated", "case_id": request.case_id, "updated": request.field}
        try:
            result = deepcopy(
                dict(self.webhook(request.model_dump(mode="json"), timeout_seconds=30))
            )
            value_hash(result)
        except Exception:
            return {"status": "unknown", "error": "webhook_outcome_unknown", "attempts": 1}
        if result.get("status") == "blocked":
            return result  # Explicit remote non-execution assertion, not a timeout.
        receipt = result.get("receipt_id")
        if result.get("status") == "completed" and isinstance(receipt, str) and receipt.strip():
            return result
        return {"status": "unknown", "error": "unconfirmed_webhook_response", "attempts": 1}

    def _build(
        self,
        run_id: UUID,
        request: CaseFileUpdate,
        decision: dict[str, Any],
        executed: bool | None,
        result: dict[str, Any],
        nonce: str,
        approved_by: str | None,
        approval_digest: str | None = None,
    ) -> WorkflowEvidenceEnvelope:
        payload = {
            "tenant_id": self.tenant_id,
            "policy_version": self.policy_version,
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
            "request_digest": request_digest(
                self.tenant_id, run_id, nonce, request, self.policy_version
            ),
            "approval_digest": approval_digest,
            "nonce": nonce,
            "public_key": base64.b64encode(_public_key_bytes(self.anchor)).decode(),
        }
        unsigned = WorkflowEvidenceEnvelope(**payload, signature="")
        signature = base64.b64encode(
            self.anchor.sign(canonical_unsigned(unsigned.model_dump()))
        ).decode()
        return unsigned.model_copy(update={"signature": signature})


__all__ = ["CaseFileUpdate", "TamilNaduWorkflow", "WorkflowEvidenceEnvelope", "verify_envelope"]
