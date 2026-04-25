import time
import os
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from localagent.cli.ipc import send_ipc_command
from localagent.cli.terminal_ui import render_airlock_modal, print_banner

console = Console()

# Custom styles for the sovereign prompt
style = Style.from_dict({
    'prompt': 'bold cyan',
    'agent': 'bold green',
    'error': 'bold red',
})

def interact_repl(timeout: int = None):
    """
    Standard REPL for the headless control surface.
    Synchronizes with the background daemon via IPC.
    """
    print_banner()
    console.print("[dim]Type '/exit' to quit, '/status' for daemon health.[/dim]\n")
    
    # Setup persistent history
    history_file = Path.home() / ".localagent" / "history"
    history_file.parent.mkdir(parents=True, exist_ok=True)
    
    session = PromptSession(
        history=FileHistory(str(history_file)),
        auto_suggest=AutoSuggestFromHistory(),
        style=style
    )

    while True:
        try:
            # 1. Prompt for user input
            text = session.prompt([('class:prompt', 'LocalAgent > ')]).strip()
            
            if not text:
                continue
            
            # 2. Internal CLI Commands
            if text.lower() in ['/exit', '/quit', 'exit', 'quit']:
                break
            if text.lower() == '/status':
                res = send_ipc_command("get_status")
                console.print(f"[bold cyan]Daemon Status:[/bold cyan] {res}")
                continue
            if text.lower() == '/airlock':
                # Force poll for airlocks
                _check_for_airlocks()
                continue

            # 3. Send message to Agent Daemon
            console.print("[italic dim]Processing...[/italic dim]")
            res = send_ipc_command("chat", {"prompt": text})
            
            if "error" in res:
                if res["error"] == "connection_failed":
                    console.print("[bold red]Error:[/bold red] Daemon is not running. Start it with 'localagent start --daemon'")
                else:
                    console.print(f"[bold red]Daemon Error:[/bold red] {res.get('detail', res['error'])}")
                continue

            # 4. Handle Response
            response = res.get("response", "")
            
            # If the response is a dict, it's a security airlock requirement
            if isinstance(response, dict) and response.get("requires_confirmation"):
                console.print("\n[bold yellow]! SECURITY AIRLOCK ACTIVATED ![/bold yellow]")
                console.print(f"[dim]Intent: {response.get('intent')} | Resource: {response.get('resource')}[/dim]")
                console.print("[italic]Authorize via '/airlock' or wait for polling...[/italic]\n")
                
                # Immediate poll
                _check_for_airlocks()
                continue
                
            console.print(f"\n[bold green]Agent:[/bold green] {response}\n")

            # Check for any background airlocks that appeared during processing
            _check_for_airlocks()

        except KeyboardInterrupt:
            continue
        except EOFError:
            break

    console.print("\n[bold cyan]Sovereign session concluded.[/bold cyan]")

def _check_for_airlocks():
    """Poll for and resolve any pending security airlocks."""
    res = send_ipc_command("get_pending")
    pending = res.get("pending", [])
    
    if not pending:
        return

    for p in pending:
        render_airlock_modal(p)
        choice = input("\nChoice [a/d/p/s]: ").strip().lower()
        
        if choice in ['a', 'd', 'p', 's']:
            send_ipc_command("confirm", {"request_id": p.get("request_id"), "choice": choice})
            console.print(f"[bold green]Decision '{choice}' transmitted to daemon.[/bold green]")
        else:
            console.print("[yellow]Invalid choice. Ignoring airlock.[/yellow]")
