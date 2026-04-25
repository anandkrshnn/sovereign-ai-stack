import sys
import os
import requests
import psutil
from rich.console import Console
from rich.table import Table
from localagent.config import Config
from localagent import __version__

console = Console()

def run_diagnose():
    """
    Standard LocalAgent v0.2 Diagnosis suite.
    Checks environment, daemon health, and isolation boundaries.
    """
    console.print(f"[bold cyan]--- LocalAgent v{__version__} Multi-Point Diagnosis ---[/bold cyan]\n")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Component", style="dim")
    table.add_column("Status")
    table.add_column("Details")

    # 1. Ollama Check
    config = Config.default()
    try:
        res = requests.get(f"{config.ollama_endpoint}/api/tags", timeout=2)
        if res.status_code == 200:
            models = [m['name'] for m in res.json().get('models', [])]
            status = "[bold green][ONLINE][/bold green]"
            detail = f"Found {len(models)} models ({config.default_model} ready)"
        else:
            status = "[bold yellow][UNHEALTHY][/bold yellow]"
            detail = f"Ollama returned {res.status_code}"
    except Exception:
        status = "[bold red][OFFLINE][/bold red]"
        detail = f"No response at {config.ollama_endpoint}"
    table.add_row("LLM Engine", status, detail)

    # 2. Daemon Check
    # Actually use our daemon helper
    from localagent.cli.daemon import get_pid_file
    pid_file = get_pid_file()
    
    daemon_status = "[bold red][FAIL][/bold red]"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text())
            if psutil.pid_exists(pid):
                daemon_status = f"[bold green][OK][/bold green] (PID {pid})"
        except: pass
    table.add_row("Agent Daemon", daemon_status, "Background state")

    # 3. Isolation (Sandbox)
    sandbox = Path(config.sandbox_root)
    if not sandbox.exists():
        try:
            sandbox.mkdir(parents=True)
            table.add_row("Sandbox Path", "[bold green][CREATED][/bold green]", f"At {sandbox}")
        except:
            table.add_row("Sandbox Path", "[bold red][ERROR][/bold red]", "Failed to create sandbox")
    else:
        table.add_row("Sandbox Path", "[bold green][READY][/bold green]", str(sandbox))

    # 4. IPC (Pipe/Socket)
    from localagent.cli.ipc import PIPE_NAME
    import time
    time.sleep(0.5) # Allow cold-start daemon to bind pipe
    
    if os.name == 'nt':
        # On Windows we check if pipe exists via a quick client test
        from localagent.cli.ipc import send_ipc_command
        res = send_ipc_command("ping")
        if res.get("status") == "ok":
            table.add_row("IPC Bridge", "[bold green][CONNECTED][/bold green]", PIPE_NAME)
        else:
            table.add_row("IPC Bridge", "[bold red][REJECTED][/bold red]", "Daemon unresponsive")
    else:
        if os.path.exists(PIPE_NAME):
            table.add_row("IPC Bridge", "[bold green][ACTIVE][/bold green]", PIPE_NAME)
        else:
            table.add_row("IPC Bridge", "[bold red][MISSING][/bold red]", "Socket not found")

    console.print(table)
    console.print("\n[dim]Run 'localagent start' to resolve most issues.[/dim]")

from pathlib import Path
