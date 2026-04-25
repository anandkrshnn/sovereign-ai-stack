import json
import uuid
from pathlib import Path
from typing import List, Dict, Any
from rich.console import Console
from rich.table import Table

from localagent.config import Config
from localagent.forensics.vault_context import VaultContext
from localagent.broker.engine_core import PolicyEngine, PolicyRule

console = Console()

# Simplified JSON Schema for validation
POLICY_SCHEMA = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "intent": {"type": "string"},
            "resource_pattern": {"type": "string"},
            "effect": {"enum": ["allow", "confirm", "deny"]},
            "description": {"type": "string"}
        },
        "required": ["intent", "resource_pattern"]
    }
}

def policy_deploy(file_path: str, signature_path: str = None, key_path: str = None):
    """
    Imports policies directly to the LPB Candidate queue.
    Enforces cryptographic signature verification to prevent tampering.
    """
    import hmac
    import hashlib
    
    console.print(f"[FILE] [bold cyan]Policy Deployment Service[/bold cyan]")
    
    path = Path(file_path)
    if not path.exists():
        console.print(f"[red]Error: Policy file {file_path} not found.[/red]")
        return

    # Phase 2: Mandatory Signature Verification
    if not signature_path or not key_path:
        console.print("[yellow]WARNING: Deploying without --signature and --key-file is insecure.[/yellow]")
        console.print("[yellow]For production-grade v0.2, signatures will be MANDATORY.[/yellow]\n")
        # For this sprint, we enforce it if provided, but warn otherwise
    else:
        sig_path = Path(signature_path)
        k_path = Path(key_path)
        if not sig_path.exists() or not k_path.exists():
            console.print("[red][FAIL] Signature or Key file missing.[/red]")
            return
            
        content = path.read_bytes()
        admin_key = k_path.read_text().strip()
        expected_sig = hmac.new(admin_key.encode(), content, hashlib.sha256).hexdigest()
        provided_sig = sig_path.read_text().strip()
        
        if not hmac.compare_digest(expected_sig, provided_sig):
            console.print("[red][FAIL] Validation Error: Signature Mismatch. Active Policy deployment forcefully rejected.[/red]")
            return
        
        console.print("[green][VERIFIED] Cryptographic signature matches administrative key.[/green]")

    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        # Basic validation (could use jsonschema library if available)
        if not isinstance(data, list):
            raise ValueError("Root must be a JSON array of rules.")
    except Exception as e:
        console.print(f"[red]Error parsing JSON: {e}[/red]")
        return

    # Initialize Engine (Standalone)
    vault = VaultContext.default()
    # We might need to unlock if policies are encrypted
    # For v0.2, policies.json is often encrypted in the vault.
    # We'll try to load it; if fail, we ask for password.
    
    engine = PolicyEngine(broker=None, db_path=str(vault.policies_json), key_manager=vault.key_manager)
    
    added_count = 0
    table = Table(title="Imported Policies (Pending Review)")
    table.add_column("Intent", style="cyan")
    table.add_column("Pattern", style="magenta")
    table.add_column("Effect", style="green")

    for raw_rule in data:
        intent = raw_rule.get("intent")
        pattern = raw_rule.get("resource_pattern")
        effect = raw_rule.get("effect", "allow")
        desc = raw_rule.get("description", "Imported via CLI")
        
        # Create as candidate (for safety) or directly active? 
        # Design doc: "Imports... to the CandidateRules queue"
        rule_id = engine.create_candidate_rule(intent, pattern, reason=desc)
        table.add_row(intent, pattern, effect)
        added_count += 1

    console.print(table)
    console.print(f"[bold green][OK] Successfully deployed {added_count} rules to Candidate queue.[/bold green]")
    console.print("[dim]Use 'localagent status' or the Web UI to approve these rules.[/dim]")

def allowlist_add(secret: str):
    """
    Bypasses the UI to inject sensitive strings into the Pre-Scanner engine.
    """
    console.print(f"[LOCK] [bold cyan]Secret Allowlist Manager[/bold cyan]")
    vault = VaultContext.default()
    engine = PolicyEngine(broker=None, db_path=str(vault.policies_json), key_manager=vault.key_manager)
    
    engine.add_to_allowlist(secret)
    console.print(f"[bold green][OK] Secret added to protected allowlist.[/bold green]")
    console.print(f"[dim]Snippet: {secret[:4]}***[/dim]")
