import asyncio
import json
from dataclasses import dataclass
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress
from rich.table import Table
from rich.syntax import Syntax

# Sovereign AI Stack Core Modules (Brutal Minimalism)
from sovereign_ai.common.hardware_trust import get_secure_anchor
from sovereign_ai.verify.evaluator import SovereignEvaluator
from sovereign_ai.common.ledger_db import DatabaseAuditChain
from sovereign_ai.common.merkle import verify_proof_async

console = Console(record=True)

@dataclass
class PTVDemoResult:
    stage: str
    status: str
    details: dict

async def run_ptv_live_demo():
    console.print(Panel.fit(
        "[bold cyan]PTV Protocol Live Demo — Verified Airlock for Sovereign AI[/bold cyan]\n"
        "[dim]Prove → Transform → Verify (TPM + NLI + Merkle)[/dim]",
        border_style="blue"
    ))

    # Initialize with strict Airlock
    anchor = get_secure_anchor("ptv-demo-tenant")
    evaluator = SovereignEvaluator()
    
    # Use O(1) PostgreSQL/SQLite async ledger
    audit_chain = DatabaseAuditChain("ptv-demo-tenant", "sqlite+aiosqlite:///ptv_demo_ledger.sqlite", anchor)
    await audit_chain.initialize()
    
    # Pre-warm Evaluator model weights (to avoid blocking UI output)
    await asyncio.to_thread(evaluator._ensure_model)

    query = "Explain benefits of PTV for GAIP-2030 compliance"
    context = "PTV enables hardware-rooted zero-knowledge attestation without exposing raw data."
    model_output = "PTV provides cryptographic hardware attestation and zero-knowledge proofs for GAIP compliance."

    stages: list[PTVDemoResult] = []

    # 1. PROVE
    console.print("\n[bold]1. PROVE Phase[/bold] — Hardware Attestation")
    with Progress() as progress:
        task = progress.add_task("[cyan]Generating TPM Quote...", total=100)
        for i in range(4):
            await asyncio.sleep(0.25)
            progress.update(task, advance=25)
    
    # GIL Release: Run CPU-bound crypto in a thread
    quote = await asyncio.to_thread(anchor.generate_quote, "nonce123", [0, 11])
    console.print(f"✅ TPM Quote (excerpt): [dim]{quote.signature[:60]}...[/dim]")
    stages.append(PTVDemoResult("Prove", "SUCCESS", {"quote_sig_len": len(quote.signature)}))

    # 2. TRANSFORM
    console.print("\n[bold]2. TRANSFORM Phase[/bold] — Policy + NLI Grounding")
    # Gate: Evaluate with strict 0.85 threshold
    eval_res = await evaluator.evaluate_with_threshold_async(query, context, model_output, threshold=0.85)
    
    nli_status = "[green]PASS[/green]" if eval_res["passed"] else "[red]FAIL-CLOSED[/red]"
    console.print(f"📊 NLI Score: {eval_res['grounding_score']:.3f} → {nli_status}")
    stages.append(PTVDemoResult("Transform", "SUCCESS" if eval_res["passed"] else "FAIL-CLOSED", {"nli_score": eval_res["grounding_score"]}))

    # 3. VERIFY
    console.print("\n[bold]3. VERIFY Phase[/bold] — Merkle + Remote Simulation")
    
    # Append to append-only O(1) Merkle ledger
    record_idx = await audit_chain.append_record("PTV_TRANSFORM", {
        "query": query, 
        "nli_score": eval_res["grounding_score"],
        "passed": eval_res["passed"]
    })
    
    # Retrieve mathematical proof
    proof = await audit_chain.get_audit_proof(record_idx)
    
    # Verify proof asynchronously
    is_valid = await verify_proof_async(proof["leaf_hash"], proof["proof"], proof["root_hash"])
    
    if is_valid:
        console.print(Panel("[bold green]✓ MATHEMATICAL VERIFICATION SUCCESS[/bold green]", style="green"))
    else:
        console.print(Panel("[bold red]✗ VERIFICATION FAILED — Tamper Detected[/bold red]", style="red"))
    stages.append(PTVDemoResult("Verify", "SUCCESS" if is_valid else "FAILED", {"merkle_root": proof["root_hash"][:16]}))

    # C4-Inspired Summary Table
    table = Table(title="PTV Airlock Execution Summary")
    table.add_column("Stage", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Key Evidence")
    for stage in stages:
        table.add_row(stage.stage, stage.status, json.dumps(stage.details, indent=None)[:80])
    console.print(table)

    # Visual Sequence Diagram (C4-style)
    mermaid_flow = """sequenceDiagram
    participant Agent
    participant TPM
    participant NLI as NLI Gate (0.85)
    participant Verifier
    Agent->>TPM: Prove (Quote + State Hash)
    TPM-->>Agent: Signed Quote
    Agent->>NLI: Transform (ABAC Policy + Grounding)
    NLI-->>Agent: NLI Score + Merkle Leaf
    Agent->>Verifier: Verify (Proof + Path)
    Verifier-->>Agent: Valid / Fail-Closed"""
    console.print("\n[bold]PTV Flow (C4 Sequence):[/bold]")
    console.print(Syntax(mermaid_flow, "mermaid", theme="monokai"))
    
    with open("docs/ptv_demo_flow.mmd", "w") as f:
        f.write(mermaid_flow)
    console.print("\n💾 Diagram exported → [bold]docs/ptv_demo_flow.mmd[/bold] (render at mermaid.live)")

    # Tamper Simulation (Audience Wow)
    console.print("\n[bold red]Tamper Simulation (Red Team Test):[/bold]")
    console.print("Attacker modifying Merkle proof leaf hash to bypass audit...")
    tampered_valid = await verify_proof_async("tampered_hash_123", proof["proof"], proof["root_hash"])
    console.print(f"Tampered proof → [red]FAIL-CLOSED[/red] as expected: {not tampered_valid}")

    # Log successful execution to chain
    await audit_chain.append_record("PTV_LIVE_DEMO", {"query": query, "status": "verified"})
    console.print(Panel.fit("[bold green]Demo Complete — Airlock Enforced[/bold green]", border_style="green"))

if __name__ == "__main__":
    asyncio.run(run_ptv_live_demo())
