"""Deterministic local orchestrator with policy, retry, approval, and evidence hooks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .adapters import AdapterError, ToolAdapter
from .models import (
    Approval,
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
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


class DeterministicOrchestrator:
    def __init__(
        self,
        adapters: Mapping[str, ToolAdapter],
        policy: Policy,
        verify: Callable[[Task, Step, Mapping[str, Any]], VerificationResult] | None = None,
        record_evidence: Callable[[EvidenceBundle], None] | None = None,
        emit: Callable[[OrchestratorEvent], None] | None = None,
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
        self._idempotent_results: dict[str, dict[str, Any]] = {}
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
        approval.approved_by = principal
        from datetime import datetime, timezone

        approval.approved_at = datetime.now(timezone.utc)

    def run(self, task: Task, steps: list[Step], run: Run | None = None) -> Run:
        run = run or Run(task_id=task.id)
        if run.state in {RunState.SUCCEEDED, RunState.FAILED, RunState.CANCELLED}:
            return run
        run.state = RunState.RUNNING
        self._event("run.started", run)
        for index, step in enumerate(steps[run.step_index :], start=run.step_index):
            if str(run.id) in self._cancelled:
                return run
            run.step_index = index
            decision = self.policy.decide(task, step.tool_call)
            self._event("policy.decided", run, step, decision=decision.model_dump())
            if not decision.allowed:
                step.tool_call.state = ToolCallState.DENIED
                run.state = RunState.FAILED
                run.error = decision.reason
                self._event("step.denied", run, step, reason=decision.reason)
                return run
            if decision.requires_approval and not self._is_approved(run, step):
                approval = Approval(run_id=run.id, step_id=step.id)
                self._approvals[str(approval.id)] = approval
                run.state = RunState.WAITING_APPROVAL
                self._event("approval.requested", run, step, approval_id=str(approval.id))
                return run
            result = self._execute_with_retry(task, run, step, decision)
            if result is None:
                return run
        run.state = RunState.SUCCEEDED
        self._event("run.succeeded", run)
        return run

    def _is_approved(self, run: Run, step: Step) -> bool:
        return any(
            approval.run_id == run.id and approval.step_id == step.id and approval.approved_at
            for approval in self._approvals.values()
        )

    def _execute_with_retry(
        self, task: Task, run: Run, step: Step, decision: PolicyDecision
    ) -> dict[str, Any] | None:
        call = step.tool_call
        key = call.idempotency_key
        if key in self._idempotent_results:
            output = self._idempotent_results[key]
        else:
            adapter = self.adapters.get(call.tool_name)
            if not adapter:
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
                    output = adapter.execute(call.arguments, call.timeout_seconds)
                    self._idempotent_results[key] = output
                    call.state = ToolCallState.SUCCEEDED
                    break
                except (AdapterError, TimeoutError) as exc:
                    call.state = (
                        ToolCallState.TIMED_OUT
                        if isinstance(exc, TimeoutError)
                        else ToolCallState.FAILED
                    )
                    if attempt == call.max_attempts:
                        run.state = RunState.FAILED
                        run.error = str(exc)
                        self._event("tool.failed", run, step, error=str(exc))
                        return None
        verification = self.verify(task, step, output)
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
