from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from typing import Dict, Any

console = Console()

def render_airlock_modal(violation: Dict[str, Any]):
    """
    Renders the Spec-compliant AIRLOCK INTERVENTION REQUIRED panel.
    """
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_row("[bold cyan]INTENT[/bold cyan]", f": {violation.get('intent', 'unknown')}")
    table.add_row("[bold cyan]RESOURCE[/bold cyan]", f": {violation.get('resource', 'unknown')}")
    table.add_row("[bold cyan]SOURCE[/bold cyan]", f": [italic]Local / CLI Prompt[/italic]")
    
    risk_color = "red" if violation.get("risk", "Low") == "High" else "yellow"
    table.add_row("[bold cyan]RISK[/bold cyan]", f": [{risk_color}]{violation.get('risk', 'Moderate')}[/{risk_color}]")

    panel = Panel(
        table,
        title="[bold red][SECURITY] AIRLOCK INTERVENTION REQUIRED[/bold red]",
        border_style="red",
        padding=(1, 2),
        expand=False
    )
    
    console.print("\n")
    console.print(panel)
    
    if violation.get("no_policy"):
        console.print("[bold yellow][!] No matching policy rule discovered.[/bold yellow]\n")
    
    console.print("What would you like to do?")
    console.print("  [bold green][a][/bold green] Approve Once (Ephemeral execution)")
    console.print("  [bold red][d][/bold red] Deny / Reject")
    console.print("  [bold blue][p][/bold blue] Promote to Always Allow")
    console.print("  [bold yellow][s][/bold yellow] Proactive Simulation Backtest")
    console.print("=" * 60)

def render_error_json(code: int, error: str, detail: str):
    """
    Machine-parsable error output for CI/CD runs.
    """
    import json
    data = {"error": error, "detail": detail, "code": code}
    print(json.dumps(data, indent=2))

def print_banner():
    """Premium startup banner for the sovereign engine."""
    console.print(Panel.fit(
        "[bold cyan]LocalAgent v0.2-RELEASE[/bold cyan]\n[dim]Sovereign Zero-Trust AI Control Surface[/dim]",
        border_style="cyan"
    ))
