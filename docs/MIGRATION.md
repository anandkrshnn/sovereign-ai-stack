# Migration from Satellite Repositories

The following satellite repositories have been **deprecated** and consolidated into the [`sovereign-ai-stack`](https://github.com/anandkrshnn/sovereign-ai-stack) monorepo:

- `local-rag`
- `local-bridge`
- `local-verify`
- `local-agent`

All active development, bug fixes, and new features will happen exclusively in the monorepo going forward.  The satellite repos are archived and will no longer receive updates.

---

## Repository Mapping

| Satellite Repo | Monorepo Path | Status |
|---|---|---|
| `local-rag` | `sovereign_ai/rag/` | Deprecated — Moved to Monorepo |
| `local-bridge` | `sovereign_ai/bridge/` | Deprecated — Moved to Monorepo |
| `local-verify` | `sovereign_ai/verify/` | Deprecated — Moved to Monorepo |
| `local-agent` | `sovereign_ai/agent/` | Deprecated — Moved to Monorepo |

---

## Installation

Installing the monorepo package gives you access to **all components** in one step:

```bash
pip install sovereign-ai-stack
```

Optional extras:

```bash
pip install "sovereign-ai-stack[agent]"   # Ed25519 signing (cryptography + keyring)
pip install "sovereign-ai-stack[bridge]"  # HTTP gateway (httpx, redis, prometheus)
pip install "sovereign-ai-stack[verify]"  # NLI grounding judge (torch, sentence-transformers)
pip install "sovereign-ai-stack[full]"    # All of the above
```

---

## What To Do

### 1. Update Your Imports

Replace old satellite-repo imports with their monorepo equivalents:

| Old import (satellite) | New import (monorepo) |
|---|---|
| `from local_rag import LocalRAG` | `from sovereign_ai.rag import RAGPipeline` |
| `from local_bridge import SovereignOrchestrator` | `from sovereign_ai.bridge import SovereignOrchestrator` |
| `from local_verify import SovereignEvaluator` | `from sovereign_ai.verify import SovereignEvaluator` |
| `from local_agent import AgentCore` | `from sovereign_ai.agent import AgentCore` |

### 2. Pin to the Latest `sovereign-ai-stack` Version

Update your `requirements.txt` or `pyproject.toml`:

```
sovereign-ai-stack>=1.0.0
```

### 3. Archive Your Local Clones of Satellite Repos

Once you have migrated your imports and confirmed everything works, archive (or delete) your local clones of the satellite repositories:

```bash
# Example — rename to signal archival
mv local-rag local-rag.ARCHIVED
mv local-bridge local-bridge.ARCHIVED
mv local-verify local-verify.ARCHIVED
mv local-agent local-agent.ARCHIVED
```

If you have any forks on GitHub, use the repository settings to mark them as **Archived**.

---

## Questions

Open an issue in the [sovereign-ai-stack repository](https://github.com/anandkrshnn/sovereign-ai-stack/issues) if you encounter migration problems.
