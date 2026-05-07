import os
import json
from pathlib import Path
from sovereign_ai import SovereignAgent, SignedAuditChain

def run_forensic_agent():
    # 1. Initialize the Forensic Agent
    # We use a local vault directory for traces and audit logs
    vault_dir = Path("data/agent_vault")
    vault_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Initializing Sovereign Agent in {vault_dir}...")
    agent = SovereignAgent(vault_root=str(vault_dir))
    
    # 2. Execute a task
    user_input = "Create a file named 'hello.txt' with the content 'Hello from Sovereign AI'"
    print(f"\nUser: {user_input}")
    
    # The agent will attempt to use 'write_file'
    # By default, it might require manual confirmation or auto-approve based on policy
    response = agent.chat(user_input)
    print(f"Agent Response: {response}")
    
    # 3. Verify the Forensic Audit Chain
    # Every decision is recorded and hashed in a chain
    trace_log = vault_dir / "traces" / "decision_traces.jsonl"
    if trace_log.exists():
        print(f"\nVerifying Forensic Audit Chain for {trace_log.name}...")
        is_valid = SignedAuditChain.verify_chain(trace_log, mode="plaintext")
        print(f"Chain Integrity Valid: {is_valid}")
        
        # Check for anchor (Ed25519 signature tip)
        anchor_file = trace_log.with_suffix(".anchor")
        if anchor_file.exists():
            print(f"Signature Anchor Found: {anchor_file.read_text()}")
    else:
        print("\nNote: Decision traces were not written (check if agent had enough iterations or errored).")

if __name__ == "__main__":
    run_forensic_agent()
