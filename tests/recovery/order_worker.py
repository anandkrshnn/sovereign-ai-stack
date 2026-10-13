"""Host worker using ordinary repository imports and the real PR #4 orchestrator."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

from sovereign_ai.orchestration import (
    AllowListPolicy,
    AttemptContext,
    DeterministicOrchestrator,
    RunState,
    SQLiteExecutionJournal,
)
from sovereign_ai.orchestration.adapters import ToolAdapter
from sovereign_ai.orchestration.models import EvidenceBundle, Run, Step, Task
from sovereign_ai.orchestration.runner import OrchestratorEvent


class OrderAdapter(ToolAdapter):
    name = "orders.create"

    def __init__(self, url: str):
        self.url = url
        self.receipts: list[dict] = []

    def execute(self, arguments, timeout_seconds):
        return self._request(dict(arguments), arguments, timeout_seconds)

    def execute_attempt(self, arguments, timeout_seconds, context: AttemptContext):
        receipt = self._request(
            {"arguments": dict(arguments), "execution": asdict(context)},
            arguments,
            timeout_seconds,
        )
        context.validate_receipt(receipt)
        return receipt

    def _request(self, body, arguments, timeout_seconds):
        request = Request(
            self.url,
            data=json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {os.environ['ORDER_TEST_GATEWAY_TOKEN']}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        # No retry loop; socket timeouts propagate as ambiguous adapter failures.
        with urlopen(request, timeout=timeout_seconds) as response:
            receipt = json.load(response)
        for field in ("tenant_id", "operation_key", "payload_digest"):
            if receipt.get(field) != arguments[field]:
                raise ValueError(f"unbound fixture receipt: {field}")
        if not receipt.get("order_id"):
            raise ValueError("missing order ID")
        self.receipts.append(receipt)
        return receipt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("url")
    parser.add_argument("report", type=Path)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--repeat-in-process", action="store_true")
    options = parser.parse_args()
    intent = json.loads(options.manifest.read_text())
    task = Task.model_validate(intent["task"])
    step = Step.model_validate(intent["step"])
    step.tool_call.timeout_seconds = options.timeout
    adapter = OrderAdapter(options.url)
    events: list[OrchestratorEvent] = []
    evidence: list[EvidenceBundle] = []
    journal = SQLiteExecutionJournal(options.manifest.parent / "execution.sqlite")
    runner = DeterministicOrchestrator(
        {adapter.name: adapter},
        AllowListPolicy({adapter.name}, tool_consequences={adapter.name: "write"}),
        emit=events.append,
        record_evidence=evidence.append,
        journal=journal,
    )
    # Actual application journal, separate from remote state and caller intent.

    def submit(run_id):
        run = Run(id=run_id, task_id=task.id)
        run = runner.run(task, [step], run)
        if run.state is RunState.WAITING_APPROVAL:
            requested = [
                event
                for event in events
                if event.event_type == "approval.requested" and event.run_id == str(run.id)
            ]
            runner.approve(requested[-1].data["approval_id"], "recovery-fixture-host")
            run = runner.run(task, [step], run)
        return run

    try:
        run = submit(intent["run_id"])
        repeated = submit(uuid4()) if options.repeat_in_process else None
    finally:
        journal.close()
    report = {
        "pid": os.getpid(),
        "state": run.state.value,
        "error": run.error,
        "attempts": run.attempts,
        "repeat_state": repeated.state.value if repeated else None,
        "receipts": adapter.receipts,
        "evidence": [item.model_dump(mode="json") for item in evidence],
        "events": [{"type": event.event_type, "run_id": event.run_id} for event in events],
    }
    # Diagnostic observations only: never read this report to drive recovery.
    options.report.write_text(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
