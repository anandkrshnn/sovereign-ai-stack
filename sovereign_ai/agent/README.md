# sovereign_ai/agent

> **Canonical home** for all code previously in the `local-agent-v0.2` satellite repository, including Ed25519 forensics.

## Purpose

`sovereign_ai.agent` is the **forensic agent layer** of the Sovereign AI Stack.  It provides:

- A sandboxed, policy-gated tool-use loop (`AgentCore`) for local file and memory operations.
- Ed25519 payload signing for non-repudiable, hardware-verifiable forensic traces.
- Encrypted vault management via `VaultContext` and `VaultKeyManager`.
- Deterministic decision tracing via `DecisionTrace`.

## Key Classes / Functions

| Symbol | Module | Description |
|---|---|---|
| `AgentCore` | `sovereign_ai.agent.core_loop` | Central orchestrator for secure, local tool-use and semantic memory recall. |
| `sign_payload` | `sovereign_ai.agent.signing` | Sign a JSON-serialised payload dict with an Ed25519 private key; returns a hex signature. |
| `AgentConfig` | `sovereign_ai.agent.config` | Agent configuration (model, paths, limits). |

## Ed25519 Forensic Signing

```python
from sovereign_ai.agent import sign_payload

signature = sign_payload(
    payload={"event": "query", "principal": "alice", "ts": 1234567890},
    private_key_path="/path/to/ed25519_private.pem",
)
print(signature)  # hex-encoded Ed25519 signature
```

`sign_payload` uses the `cryptography` library (`pip install cryptography`).  The payload is serialised to canonical JSON (sorted keys) before signing to ensure cross-platform reproducibility.

## Quick Start

```python
from sovereign_ai.agent import AgentCore

agent = AgentCore()
result = agent.run("Summarise the top 3 documents in the vault.")
```

## Migration Note

This module is the **canonical home** for all code previously in the `local-agent-v0.2` satellite repository.  If you were importing from `local_agent`, update your imports to use `sovereign_ai.agent` instead.

See [docs/MIGRATION.md](../../docs/MIGRATION.md) for full migration instructions.
