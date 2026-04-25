import typer
from rich.console import Console
from rich.panel import Panel
from typing import Optional

# Lazy imports to keep CLI responsive
# from localagent.cli.daemon import start_daemon_process, status_daemon, stop_daemon
# from localagent.cli.policy import policy_deploy
# from localagent.cli.forensics import forensics_export
# from localagent.cli.interact import interact_repl

app = typer.Typer(
    name="localagent",
    help="Zero-Trust Sovereign AI - Headless Control Surface",
    no_args_is_help=True,
    rich_markup_mode="rich"
)
console = Console()

@app.command()
def start(
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run LocalAgent in the background as a daemon"),
    api_token: str = typer.Option(None, "--api-token", help="Specify a static API token for the daemon"),
    port: int = typer.Option(8000, "--port", "-p", help="Port to bind the API to"),
):
    """Start the LocalAgent core and dashboard."""
    from localagent.cli.daemon import start_daemon_process
    if daemon:
        start_daemon_process(token=api_token, port=port)
    else:
        # Foreground mode
        from localagent.api.app import run_serve
        console.print(Panel("[bold green]Starting LocalAgent in foreground mode...[/bold green]"))
        run_serve(host="127.0.0.1", port=port)

@app.command()
def status():
    """Check the health and sync status of the background daemon."""
    from localagent.cli.daemon import status_daemon
    status_daemon()

@app.command()
def stop():
    """Gracefully stop the background daemon."""
    from localagent.cli.daemon import stop_daemon
    stop_daemon()

@app.command(name="policy")
def policy_cmd(
    file_path: str = typer.Argument(..., help="Path to rules.json to deploy"),
    signature: Optional[str] = typer.Option(None, "--signature", help="Cryptographic signature file (.sig)"),
    key_file: Optional[str] = typer.Option(None, "--key-file", help="Path to administration key for verification"),
):
    """Deploy security policies with mandatory cryptographic signature verification."""
    from localagent.cli.policy import policy_deploy
    policy_deploy(file_path, signature_path=signature, key_path=key_file)

@app.command(name="allowlist")
def allowlist_cmd(
    secret: str = typer.Argument(..., help="Secret string to allowlist (e.g. AWS Key, API Token)"),
):
    """Bypass the UI to inject sensitive strings into the Pre-Scanner engine."""
    from localagent.cli.policy import allowlist_add
    allowlist_add(secret)

@app.command(name="forensics")
def forensics_cmd(
    format: str = typer.Option("json", "--format", help="Export format (json|csv)"),
    since: str = typer.Option("24h", "--since", help="Time window to export"),
    out: str = typer.Option("export.json", "--out", help="Output file path"),
    key_file: Optional[str] = typer.Option(None, "--key-file", help="Path to vault.key for headless decryption"),
):
    """Bulk export trace forensics without starting the web UI."""
    from localagent.cli.forensics import forensics_export
    forensics_export(format, since, out, key_file)

@app.command()
def interact(
    timeout: int = typer.Option(15, "--timeout", help="Reject AirLock requests after N seconds"),
    no_timeout: bool = typer.Option(False, "--no-timeout", help="Disable reject timeout for testing"),
):
    """Enter the Interactive Terminal REPL with integrated AirLock support."""
    from localagent.cli.interact import interact_repl
    interact_repl(timeout if not no_timeout else None)

@app.command()
def diagnose():
    """Run a full check of the local environment and daemon health."""
    from localagent.cli.diagnose import run_diagnose
    run_diagnose()

@app.command(name="request")
def request_cmd(
    intent: str = typer.Argument(..., help="Agent intent (e.g. read_file)"),
    resource: str = typer.Argument(..., help="Target resource path"),
    context: str = typer.Option("", "--context", help="Optional data context for scanning"),
    audit_log: str = typer.Option("audit.jsonl", "--audit-log", help="Path to audit log"),
    profile: str = typer.Option("plaintext", "--profile", help="Security profile (plaintext|encrypted)"),
):
    """Execute a single agent intent through the sovereign firewall."""
    from pathlib import Path
    import json
    import sys
    from localagent.broker.engine import LocalPermissionBroker
    from localagent.forensics.vault_key_manager import VaultKeyManager

    class MockNullKeyManager:
        def is_encrypted(self): return False
        def encrypt(self, d): return d
        def decrypt(self, d): return d

    audit_path = Path(audit_log)
    if profile == 'encrypted':
        km = VaultKeyManager(Path('.'), password='demo')
        broker = LocalPermissionBroker(str(audit_path), key_manager=km)
    else:
        broker = LocalPermissionBroker(str(audit_path), key_manager=MockNullKeyManager())
    
    result = broker.request_permission(intent, resource, context=context)
    console.print(json.dumps(result, indent=2))
    
    if not result.get("granted"):
        sys.exit(1)

@app.command(name="read_file")
def read_file_alias(
    resource: str = typer.Argument(..., help="Path to read"),
    context: str = typer.Option("", "--context"),
):
    """Alias for 'request read_file'."""
    request_cmd("read_file", resource, context=context)

@app.command(name="write_file")
def write_file_alias(
    resource: str = typer.Argument(..., help="Path to write"),
    context: str = typer.Option("", "--context"),
):
    """Alias for 'request write_file'."""
    request_cmd("write_file", resource, context=context)

if __name__ == "__main__":
    app()
