# sovereign_ai/bridge

> **Canonical home** for all code previously in the `local-bridge` satellite repository.

## Purpose

`sovereign_ai.bridge` is the **local bridge** between the sovereign agent layer and the RAG / verify layers.  It exposes an OpenAI-compatible HTTP gateway (`/v1/chat/completions`) that:

- Routes chat requests through the governed RAG pipeline.
- Optionally verifies grounding with the NLI-based verify layer.
- Enforces per-tenant ABAC policies and audit-logs every inference event.
- Emits Prometheus metrics via `/metrics`.

## Key Classes / Functions

| Symbol | Module | Description |
|---|---|---|
| `app` | `sovereign_ai.bridge.main` | FastAPI application — the main HTTP gateway. |
| `SovereignOrchestrator` | `sovereign_ai.bridge.orchestrator` | Multi-tenant orchestrator that pools RAG resources per tenant. |
| `ChatCompletionRequest` | `sovereign_ai.bridge.schemas` | Pydantic model for OpenAI-compatible chat requests. |
| `ChatCompletionResponse` | `sovereign_ai.bridge.schemas` | Pydantic model for chat responses. |
| `ChatMessage` | `sovereign_ai.bridge.schemas` | Single chat turn (role + content). |
| `BackendType` | `sovereign_ai.bridge.schemas` | Enum of supported LLM backends (`ollama`, `vllm`). |
| `BackendConfig` | `sovereign_ai.bridge.schemas` | Configuration for a single backend endpoint. |
| `SovereignMetrics` | `sovereign_ai.bridge.metrics` | Prometheus metrics collector for the bridge. |

## Quick Start

```python
from sovereign_ai.bridge import SovereignOrchestrator, ChatCompletionRequest

orchestrator = SovereignOrchestrator(base_dir="data")
```

Or run the server directly:

```bash
sovereign-ai bridge
```

## Migration Note

This module is the **canonical home** for all code previously in the `local-bridge` satellite repository.  If you were importing from `local_bridge`, update your imports to use `sovereign_ai.bridge` instead.

See [docs/MIGRATION.md](../../docs/MIGRATION.md) for full migration instructions.
