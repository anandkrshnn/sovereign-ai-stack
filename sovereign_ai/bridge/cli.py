import typer
import os
from rich.console import Console
from rich.panel import Panel
from .audit import AuditLogger

app = typer.Typer(help="local-bridge — GAIP-2030 Developer Gateway Control Plane")
console = Console()

@app.command()
def start(
    port: int = typer.Option(8000, "--port", help="Port to run the gateway on"),
    db: str = typer.Option("enclave.db", "--db", help="Path to sovereign database"),
    policies: str = typer.Option("policies", "--policies", help="Path to policy root")
):
    """Launch the GAIP-2030 Developer Gateway."""
    os.environ["LOCAL_RAG_DB"] = db
    os.environ["SOVEREIGN_POLICIES"] = policies
    os.environ["PORT"] = str(port)
    
    from .server import main
    main()

@app.command()
def verify(
    log_path: str = typer.Option("sovereign_bridge_audit.jsonl", "--log-path", help="Path to bridge audit log")
):
    """Verify the integrity of the Master Forensic Chain."""
    logger = AuditLogger(log_path)
    with console.status("Verifying master forensic chain..."):
        is_valid, report = logger.verify_integrity()
    
    if is_valid:
        console.print(Panel(report, title="Master Forensic Integrity Verified", border_style="green"))
    else:
        console.print(Panel(report, title="INTEGRITY BREAK DETECTED", border_style="red"))
        raise typer.Exit(1)

def main():
    app()

if __name__ == "__main__":
    main()
