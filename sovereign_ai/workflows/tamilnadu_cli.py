"""Minimal operator CLI for the Tamil Nadu workflow (simulator only)."""

import json
from pathlib import Path

import click

from evidence_envelope import CaseFileUpdate, WorkflowEvidenceEnvelope

from ..common.hardware_trust import SoftwareSimulatorAnchor
from .tamilnadu_seva import TamilNaduWorkflow


def _request(destructive: bool = False) -> CaseFileUpdate:
    return CaseFileUpdate(
        case_id="TN-ES-1001",
        field="document_reference" if destructive else "status",
        value="delete documents" if destructive else "documents_verified",
        entity_id="citizen-42",
    )


@click.group()
def main() -> None:
    """Run the constrained Tamil Nadu case-file workflow."""


@main.command()
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--deny", is_flag=True, help="Submit a destructive action that must be blocked.")
def submit(output: Path, deny: bool) -> None:
    flow = TamilNaduWorkflow(SoftwareSimulatorAnchor("tn-cli"))
    envelope = flow.submit(_request(destructive=deny))
    output.write_text(envelope.model_dump_json(indent=2), encoding="utf-8")
    click.echo(f"submitted run {envelope.run_id}; policy_allowed={envelope.policy_allowed}")


@main.command()
@click.option("--input", "input_path", type=click.Path(exists=True, path_type=Path), required=True)
@click.option("--output", type=click.Path(path_type=Path), required=True)
@click.option("--principal", required=True)
def approve(input_path: Path, output: Path, principal: str) -> None:
    pending = WorkflowEvidenceEnvelope.model_validate_json(input_path.read_text(encoding="utf-8"))
    flow = TamilNaduWorkflow(SoftwareSimulatorAnchor("tn-cli"))
    flow._pending[str(pending.run_id)] = pending
    envelope = flow.approve_and_execute(pending.run_id, principal)
    output.write_text(envelope.model_dump_json(indent=2), encoding="utf-8")
    click.echo(f"completed run {envelope.run_id}; executed={envelope.executed}")


if __name__ == "__main__":
    main()
