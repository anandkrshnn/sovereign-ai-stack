import os
import sys
import subprocess
import psutil
import signal
import time
from pathlib import Path
from typing import Optional
from rich.console import Console

console = Console()

def get_daemon_dir() -> Path:
    """Standard global state directory for LocalAgent (cross-platform home)."""
    env_home = os.environ.get("LOCALAGENT_HOME")
    if env_home:
        path = Path(env_home)
    else:
        path = Path.home() / ".localagent"
    
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_pid_file() -> Path:
    return get_daemon_dir() / "localagent.pid"

def get_log_file() -> Path:
    return get_daemon_dir() / "localagent_daemon.log"

def start_daemon_process(token: Optional[str] = None, port: int = 8000) -> None:
    """Launch LocalAgent as a background daemon using DETACHED_PROCESS on Windows."""
    pid_file = get_pid_file()
    log_file = get_log_file()
    
    if pid_file.exists():
        try:
            existing_pid = int(pid_file.read_text())
            if psutil.pid_exists(existing_pid):
                console.print(f"[bold red][FAIL] Daemon already running (PID {existing_pid})[/bold red]")
                return
        except ValueError:
            pass # Stale/corrupt PID file
    
    # Build daemon command targeting the app's main entry point
    # We use -m localagent.api.app to trigger the API server
    cmd = [
        sys.executable, "-m", "localagent.api.app",
        "--host", "127.0.0.1",
        "--port", str(port),
        "--daemon-mode"
    ]
    if token:
        cmd.extend(["--api-token", token])
    
    console.print(f"[*] Starting daemon via: [dim]{' '.join(cmd)}[/dim]")
    
    # Prepare redirection for logs
    log_handle = open(log_file, "a", encoding="utf-8")
    log_handle.write(f"\n--- Daemon Session Started: {time.ctime()} ---\n")
    log_handle.flush()

    # Platform-specific detachment
    if os.name == "nt":
        # Windows creation flags for a truly headless background process
        # DETACHED_PROCESS (0x08) | CREATE_NEW_PROCESS_GROUP (0x0200) | CREATE_NO_WINDOW (0x08000000)
        flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP | 0x08000000
        proc = subprocess.Popen(
            cmd,
            creationflags=flags,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            close_fds=True,
            shell=False
        )
    else:
        # Unix/Linux backgrounding
        proc = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True
        )
    
    # Write PID file
    pid_file.write_text(str(proc.pid))
    console.print(f"[bold green][OK] Daemon started (PID {proc.pid}).[/bold green]")
    console.print(f"Log: [blue]{log_file}[/blue]")

def status_daemon() -> None:
    """Check if daemon is running and responsive."""
    pid_file = get_pid_file()
    if not pid_file.exists():
        console.print("[yellow][FAIL] No daemon PID file found.[/yellow]")
        return
    
    try:
        pid = int(pid_file.read_text())
        if psutil.pid_exists(pid):
            p = psutil.Process(pid)
            if p.is_running():
                uptime = time.time() - p.create_time()
                console.print(f"[bold green][RUNNING] Daemon running (PID {pid})[/bold green]")
                console.print(f"Uptime: {uptime/60:.1f} minutes")
                # In Phase 2, we will add an IPC ping here
                return
        
        console.print(f"[red][OFFLINE] Daemon not running (PID {pid} stale). Cleaning up.[/red]")
        pid_file.unlink()
    except Exception as e:
        console.print(f"[red]Error checking status: {e}[/red]")

def stop_daemon() -> None:
    """Gracefully stop the daemon."""
    pid_file = get_pid_file()
    if not pid_file.exists():
        console.print("[yellow]No active daemon PID found.[/yellow]")
        return
    
    try:
        pid = int(pid_file.read_text())
        if psutil.pid_exists(pid):
            console.print(f"Stopping daemon (PID {pid})...")
            p = psutil.Process(pid)
            
            # Try SIGTERM first
            p.terminate()
            try:
                p.wait(timeout=5)
            except psutil.TimeoutExpired:
                console.print("[yellow]Graceful stop timed out. Forced kill...[/yellow]")
                p.kill()
            
            console.print(f"[bold green][STOP] Daemon stopped.[/bold green]")
        else:
            console.print("[yellow]Stale PID discovered. Cleaning up.[/yellow]")
        
        pid_file.unlink()
    except Exception as e:
        console.print(f"[red]Error stopping daemon: {e}[/red]")
