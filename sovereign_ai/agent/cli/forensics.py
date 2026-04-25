import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from rich.console import Console
from rich.prompt import Prompt
from datetime import datetime, timedelta

from localagent.forensics.vault_context import VaultContext
from localagent.config import Config

console = Console()

def forensics_export(
    export_format: str = "json",
    since: str = "24h",
    out_path: str = "export.json",
    key_file: Optional[str] = None
):
    """
    Standalone forensics utility. 
    Decrypts and filters audit logs without requiring the agent daemon.
    """
    console.print(f"[STATUS] [bold cyan]Forensics Export Service[/bold cyan]")
    
    # 1. Resolve Vault and Storage
    vault = VaultContext.default()
    log_path = vault.audit_log
    
    if not log_path.exists():
        console.print(f"[red]Error: Audit log not found at {log_path}[/red]")
        return

    # 2. Decryption Layer
    password = None
    if key_file:
        key_path = Path(key_file)
        if key_path.exists():
            password = key_path.read_text().strip()
        else:
            console.print(f"[yellow]Warning: Key file {key_file} not found. Defaulting to prompt.[/yellow]")
    
    # If no key file or key file missing, prompt if salt exists (meaning encryption might be on)
    salt_path = vault.vault_root / ".vault_salt"
    if not password and salt_path.exists():
        password = Prompt.ask("Enter vault password for trace decryption", password=True)

    vault.unlock(password)
    
    # 3. Time Filtering Logic
    try:
        if since.endswith("h"):
            delta = timedelta(hours=int(since[:-1]))
        elif since.endswith("d"):
            delta = timedelta(days=int(since[:-1]))
        elif since.endswith("m"):
            delta = timedelta(minutes=int(since[:-1]))
        else:
            delta = timedelta(hours=24)
        
        start_time = datetime.utcnow() - delta
    except ValueError:
        console.print("[red]Invalid time format for --since (use 24h, 7d, etc.). Defaulting to 24h.[/red]")
        start_time = datetime.utcnow() - timedelta(hours=24)

    # 4. Processing Loop
    exported_entries = []
    skipped_count = 0
    
    console.print(f"Reading {log_path}...")
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line: continue
                
                try:
                    # Decrypt if key_manager is active
                    decrypted = vault.key_manager.decrypt(line)
                    entry = json.loads(decrypted)
                    
                    # Filtering
                    ts_str = entry.get("timestamp")
                    if ts_str:
                        entry_time = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)
                        if entry_time < start_time:
                            skipped_count += 1
                            continue
                    
                    exported_entries.append(entry)
                except Exception:
                    # Decryption failed or JSON corrupt
                    continue
    except Exception as e:
        console.print(f"[red]Error reading audit log: {e}[/red]")
        return

    # 5. Output
    if export_format.lower() == "json":
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(exported_entries, f, indent=2)
    else:
        # Simple CSV fallback
        import csv
        if exported_entries:
            keys = exported_entries[0].keys()
            with open(out_path, 'w', encoding='utf-8', newline='') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(exported_entries)

    console.print(f"[bold green][OK] Export Complete.[/bold green]")
    console.print(f"Statistics: Total Entries: {len(exported_entries)} (Skipped {skipped_count} older entries)")
    console.print(f"Output saved to: [blue]{out_path}[/blue]")
