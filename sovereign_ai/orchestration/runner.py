"""Deterministic local orchestrator with policy, retry, approval, and evidence hooks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock
from typing import Any
from uuid import UUID

from .adapters import RetryableAdapterError, ToolAdapter
from .journal import JournalConflict, SQLiteExecutionJournal
from .models import (
    Approval,
    AttemptEvidenceBundle,
    EvidenceBundle,
    PolicyDecision,
    Run,
    RunState,
    Step,
    Task,
    ToolCallState,
    VerificationResult,
)
from .policy import Policy


@dataclass(frozen=True)
class OrchestratorEvent:
    event_type: str
    run_id: str
    step_id: str | None
    data: dict[str, Any]


def _digest(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass
class _ExecutionRecord:
    request_digest: str
    state: ToolCallState
    output: dict[str, Any] | None = None


class DeterministicOrchestrator:
    def __init__(
        self,
        adapters: Mapping[str, ToolAdapter],
        policy: Policy,
        verify: Callable[[Task, Step, Mapping[str, Any]], VerificationResult] | None = None,
        record_evidence: Callable[[EvidenceBundle], None] | None = None,
        emit: Callable[[OrchestratorEvent], None] | None = None,
        approval_ttl_seconds: float = 300,
        journal: SQLiteExecutionJournal | None = None,
    ):
        self.adapters = dict(adapters)
        self.policy = policy
        self.verify = verify or (
            lambda _task, _step, _output: VerificationResult(
                passed=True, reason="no semantic verifier configured"
            )
        )
        self.record_evidence = record_evidence
        self.emit = emit
        self.journal = journal
        if not 0 < approval_ttl_seconds <= 3600:
            raise ValueError("approval_ttl_seconds must be between 0 and 3600")
        self.approval_ttl_seconds = approval_ttl_seconds
        self._idempotent_results: dict[tuple[str, str, str], _ExecutionRecord] = {}
        self._execution_lock = RLock()
        self._approvals: dict[str, Approval] = {}
        self._cancelled: set[str] = set()

    def _event(self, event_type: str, run: Run, step: Step | None = None, **data: Any) -> None:
        if self.emit:
            self.emit(
                OrchestratorEvent(event_type, str(run.id), str(step.id) if step else None, data)
            )

    def cancel(self, run: Run) -> None:
        self._cancelled.add(str(run.id))
        if run.state in {RunState.CREATED, RunState.RUNNING, RunState.WAITING_APPROVAL}:
            run.state = RunState.CANCELLED
            self._event("run.cancelled", run)

    def approve(self, approval_id: str, principal: str) -> None:
        approval = self._approvals[approval_id]
        if not principal.strip():
            raise ValueError("An authenticated, nonempty host principal is required")
        if approval.expires_at is None or datetime.now(timezone.utc) >= approval.expires_at:
            raise ValueError("Approval expired")
        approval.approved_by = principal
        approval.approved_at = datetime.now(timezone.utc)

    def run(self, task: Task, steps: list[Step], run: Run | None = None) -> Run:
        run = run or Run(task_id=task.id)
        if run.task_id != task.id:
            raise ValueError("Run belongs to another task")
        if run.state in {
            RunState.SUCCEEDED,
            RunState.FAILED,
            RunState.CANCELLED,
            RunState.OUTCOME_UNKNOWN,
        }:
            return run
        run.state = RunState.RUNNING
        self._event("run.started", run)
        for index, original_step in enumerate(steps[run.step_index :], start=run.step_index):
            if str(run.id) in self._cancelled:
                return run
            run.step_index = index
            # Freeze this dispatch's inputs against caller/event-hook mutation.
            execution_task = task.model_copy(deep=True)
            step = original_step.model_copy(deep=True)
            decision = self.policy.decide_step(execution_task, step)
            self._event("policy.decided", run, step, decision=decision.model_dump())
            if not decision.allowed:
                step.tool_call.state = ToolCallState.DENIED
                original_step.tool_call.state = step.tool_call.state
                run.state = RunState.FAILED
                run.error = decision.reason
                self._event("step.denied", run, step, reason=decision.reason)
                return run
            try:
                request_digest = self._approval_digest(execution_task, run, step, decision)
            except (TypeError, ValueError):
                original_step.tool_call.state = ToolCallState.DENIED
                run.state = RunState.FAILED
                run.error = "noncanonical_request"
                self._event("step.denied", run, step, reason=run.error)
                return run
            matching = [
                approval
                for approval in self._approvals.values()
                if approval.run_id == run.id and approval.step_id == step.id
            ]
            approved = next((a for a in matching if a.approved_at is not None), None)
            if approved is not None and (
                approved.request_digest != request_digest
                or approved.expires_at is None
                or datetime.now(timezone.utc) >= approved.expires_at
            ):
                step.tool_call.state = ToolCallState.DENIED
                original_step.tool_call.state = step.tool_call.state
                run.state = RunState.FAILED
                run.error = "approval_request_changed_or_expired"
                self._event("step.denied", run, step, reason=run.error)
                return run
            if decision.requires_approval and approved is None:
                approval = next(
                    (
                        a
                        for a in matching
                        if a.request_digest == request_digest
                        and a.expires_at is not None
                        and datetime.now(timezone.utc) < a.expires_at
                    ),
                    None,
                )
                if approval is None:
                    approval = Approval(
                        run_id=run.id,
                        step_id=step.id,
                        request_digest=request_digest,
                        expires_at=datetime.now(timezone.utc)
                        + timedelta(seconds=self.approval_ttl_seconds),
                    )
                    self._approvals[str(approval.id)] = approval
                run.state = RunState.WAITING_APPROVAL
                assert approval.expires_at is not None
                self._event(
                    "approval.requested",
                    run,
                    step,
                    approval_id=str(approval.id),
                    request_digest=request_digest,
                    expires_at=approval.expires_at.isoformat(),
                )
                return run
            result = self._execute_with_retry(execution_task, run, step, decision)
            original_step.tool_call.state = step.tool_call.state
            if result is None:
                return run
        run.state = RunState.SUCCEEDED
        self._event("run.succeeded", run)
        return run

    def _approval_digest(self, task: Task, run: Run, step: Step, decision: PolicyDecision) -> str:
        return _digest(
            {
                "tenant_id": task.tenant_id,
                "agent_id": str(task.agent_id),
                "task_id": str(task.id),
                "run_id": str(run.id),
                "step_id": str(step.id),
                "tool_call": step.tool_call.model_dump(mode="json", exclude={"state"}),
                "host_consequence": step.consequence,
                "policy": decision.model_dump(mode="json"),
            }
        )

    def _execute_with_retry(
        self, task: Task, run: Run, step: Step, decision: PolicyDecision
    ) -> dict[str, Any] | None:
        call = step.tool_call
        key = (task.tenant_id, call.tool_name, call.idempotency_key)
        request_digest = _digest(
            {
                "arguments": call.arguments,
                "host_consequence": step.consequence,
                "policy_consequence": decision.consequence,
            }
        )
        if self.journal is not None:
            return self._execute_durably(task, run, step, decision, request_digest)
        with self._execution_lock:
            cached = self._idempotent_results.get(key)
            if cached is not None and cached.request_digest != request_digest:
                call.state = ToolCallState.DENIED
                run.state = RunState.FAILED
                run.error = "idempotency_input_conflict"
                self._event("step.denied", run, step, reason=run.error)
                return None
            if cached is not None and cached.state != ToolCallState.SUCCEEDED:
                self._unknown(run, step, "prior_execution_in_flight_or_unknown")
                return None
            if cached is not None:
                if cached.output is None:
                    self._unknown(run, step, "missing_cached_confirmation")
                    return None
                output = deepcopy(cached.output)
                call.state = ToolCallState.SUCCEEDED
            else:
                # Reserve before dispatch, including for reentrant/concurrent callers.
                self._idempotent_results[key] = _ExecutionRecord(
                    request_digest, ToolCallState.RUNNING
                )
        if cached is None:
            adapter = self.adapters.get(call.tool_name)
            if not adapter:
                with self._execution_lock:
                    del self._idempotent_results[key]
                call.state = ToolCallState.DENIED
                run.state = RunState.FAILED
                run.error = "tool_adapter_not_registered"
                return None
            call.state = ToolCallState.APPROVED
            for attempt in range(1, call.max_attempts + 1):
                run.attempts += 1
                call.state = ToolCallState.RUNNING
                self._event("tool.started", run, step, attempt=attempt)
                try:
                    output = deepcopy(
                        adapter.execute(deepcopy(call.arguments), call.timeout_seconds)
                    )
                    if not isinstance(output, dict):
                        raise TypeError("Adapter response must be a JSON object")
                    _digest(output)  # Never certify an unserializable/NaN result.
                    with self._execution_lock:
                        self._idempotent_results[key] = _ExecutionRecord(
                            request_digest, ToolCallState.SUCCEEDED, deepcopy(output)
                        )
                    call.state = ToolCallState.SUCCEEDED
                    break
                except RetryableAdapterError as exc:
                    call.state = ToolCallState.FAILED
                    if attempt == call.max_attempts:
                        with self._execution_lock:
                            del self._idempotent_results[key]  # No effect was guaranteed.
                        run.state = RunState.FAILED
                        run.error = str(exc)
                        self._event("tool.failed", run, step, error=str(exc))
                        return None
                except Exception as exc:
                    # A timeout, generic adapter failure, or malformed response may
                    # follow a committed effect. Do NOT infer non-execution or retry.
                    with self._execution_lock:
                        self._idempotent_results[key] = _ExecutionRecord(
                            request_digest, ToolCallState.OUTCOME_UNKNOWN
                        )
                    self._unknown(run, step, str(exc))
                    return None
        verification = self.verify(
            task.model_copy(deep=True), step.model_copy(deep=True), deepcopy(output)
        )
        if not verification.passed:
            run.state = RunState.FAILED
            run.error = verification.reason
            self._event("verification.failed", run, step, reason=verification.reason)
            return None
        evidence = EvidenceBundle(
            run_id=run.id,
            step_id=step.id,
            tool_call_id=call.id,
            input_hash=_digest(call.arguments),
            output_hash=_digest(output),
            policy=decision,
            verification=verification,
        )
        evidence.record_hash = _digest(evidence.model_dump(mode="json"))
        if self.record_evidence:
            self.record_evidence(evidence)
        self._event("tool.succeeded", run, step, evidence=evidence.model_dump(mode="json"))
        return output

    def _execute_durably(
        self, task: Task, run: Run, step: Step, decision: PolicyDecision, request_digest: str
    ) -> dict[str, Any] | None:
        assert self.journal is not None
        call = step.tool_call
        adapter = self.adapters.get(call.tool_name)
        try:
            record = self.journal.prepare(
                (task.tenant_id, call.tool_name, call.idempotency_key), request_digest
            )
        except JournalConflict:
            call.state = ToolCallState.DENIED
            run.state = RunState.FAILED
            run.error = "idempotency_input_conflict"
            self._event("step.denied", run, step, reason=run.error)
            return None
        except Exception as exc:
            self._unknown(run, step, f"journal_unavailable:{exc}")
            return None
        context = record.context
        if record.state in {"in_flight", "outcome_unknown"}:
            self._unknown(run, step, "prior_execution_in_flight_or_unknown")
            return None
        if record.state != "succeeded" and (
            adapter is None or type(adapter).execute_attempt is ToolAdapter.execute_attempt
        ):
            call.state = ToolCallState.DENIED
            run.state = RunState.FAILED
            run.error = "attempt_bound_adapter_required"
            self._event("step.denied", run, step, reason=run.error)
            return None
        try:
            if record.state == "succeeded":
                if record.output is None or record.evidence is None:
                    raise ValueError("missing_durable_confirmation")
                output = deepcopy(record.output)
                self.journal.validate_confirmation(context, output, record.evidence)
            else:
                assert adapter is not None
                if not self.journal.begin_dispatch(context):
                    self._unknown(run, step, "dispatch_barrier_not_owned")
                    return None
                run.attempts += 1
                call.state = ToolCallState.RUNNING
                self._event(
                    "tool.started",
                    run,
                    step,
                    attempt_id=context.attempt_id,
                    owner_generation=context.owner_generation,
                )
                output = deepcopy(
                    adapter.execute_attempt(deepcopy(call.arguments), call.timeout_seconds, context)
                )
                if not isinstance(output, dict):
                    raise TypeError("Adapter response must be a JSON object")
                _digest(output)
                context.validate_receipt(output)
            verification = self.verify(
                task.model_copy(deep=True), step.model_copy(deep=True), deepcopy(output)
            )
            evidence = AttemptEvidenceBundle(
                tenant_id=task.tenant_id,
                tool_name=call.tool_name,
                operation_key=call.idempotency_key,
                request_digest=request_digest,
                attempt_id=UUID(context.attempt_id),
                owner_generation=context.owner_generation,
                run_id=run.id,
                step_id=step.id,
                tool_call_id=call.id,
                input_hash=_digest(call.arguments),
                output_hash=_digest(output),
                policy=decision,
                verification=verification,
            )
            evidence.record_hash = _digest(evidence.model_dump(mode="json"))
            if record.state != "succeeded" and not self.journal.complete(
                context, output, evidence.model_dump(mode="json")
            ):
                raise ValueError("completion_not_owned")
        except Exception as exc:
            # Even legacy RetryableAdapterError lacks attempt-bound terminal proof.
            # No safe-retry or reconciliation capability exists in this first slice.
            if record.state != "succeeded":
                try:
                    self.journal.mark_unknown(context, str(exc))
                except Exception:
                    pass  # The committed in_flight barrier remains recoverable as unknown.
            self._unknown(run, step, str(exc))
            return None
        call.state = ToolCallState.SUCCEEDED
        if not verification.passed:
            run.state = RunState.FAILED
            run.error = verification.reason
            self._event("verification.failed", run, step, reason=verification.reason)
            return None
        if self.record_evidence:
            self.record_evidence(evidence)
        self._event("tool.succeeded", run, step, evidence=evidence.model_dump(mode="json"))
        return output

    def _unknown(self, run: Run, step: Step, reason: str) -> None:
        step.tool_call.state = ToolCallState.OUTCOME_UNKNOWN
        run.state = RunState.OUTCOME_UNKNOWN
        run.error = reason
        self._event("tool.outcome_unknown", run, step, reason=reason)
