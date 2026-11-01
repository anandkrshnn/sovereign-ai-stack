# Experimental write-admission boundary

## Supported generic tool execution

The supported entry point for generic adapter writes is
`sovereign_ai.orchestration.ProductOrchestrator`.

At construction it:

- Requires `AllowListPolicy`, so tool admission uses the existing host
  consequence classification rather than inventing a second registry.
- Requires a trusted consequence for every allowlisted tool. Missing or
  unknown classifications fail construction.
- Rejects configuration with a `write` or `destructive` tool when no
  `SQLiteExecutionJournal` is supplied.
- Allows read-only tool configurations without a journal.

At dispatch, a step classified as `write` or `destructive` is rejected with
`durable_journal_required_for_write` before adapter execution if a journal is
absent. This is defense in depth for a read-configured tool whose host step
consequence is escalated to a write. Caller-provided consequence hints cannot
downgrade the host/policy classification.

An accepted `AllowListPolicy` subclass may add restrictions, but cannot waive
the product boundary. Before approval, `ProductOrchestrator` independently
applies the base allowlist/host classification and combines it with any
stronger subclass decision. Host- or registry-classified writes still require
approval and a journal even if the subclass reports `read` or omits its
consequence. The dispatch guard also checks the host step independently.

Writes with a journal still require the existing attempt-bound adapter
capability and single-host POSIX SQLite constraints. This does not claim
provider validation, production readiness, exactly-once delivery, reconciliation,
or independent remote credential isolation.

## Route inventory

| Route | Behavior and boundary |
| --- | --- |
| `ProductOrchestrator` | Supported entry point for generic adapter writes; all allowed tools require a host consequence classification and writes require `SQLiteExecutionJournal`. |
| `DeterministicOrchestrator` | Low-level compatibility API. Its in-memory execution cache remains volatile; volatile writes are unsupported as product writes. A warning is emitted when used without a journal. |
| `VolatileOrchestrator` | Explicit test/development-only alternative. It logs a warning. It cannot be passed as a mode to `ProductOrchestrator`; that entry point has no volatile escape option. |
| `HttpToolAdapter`, `CliToolAdapter`, `McpToolAdapter`, `N8nWebhookAdapter` | Adapter implementations are capabilities, not admission gates. Use them only through `ProductOrchestrator` for supported writes; direct adapter invocation or low-level volatile use is unsupported for product writes. |
| `sovereign_ai.cli` / `SovereignPipeline` | Query, verification, and local ingestion surface; not an order/tool-runner admission boundary. Local vector-store writes are outside this journal contract. |
| `TamilNaduWorkflow` and its CLI | Separate signed-evidence workflow. The CLI defaults to a simulator; an SDK-supplied webhook is a direct, in-process callback with no SQLite execution journal. Neither is supported as the durable generic order-write route. |
| `SovereignLangChainGuard` | Verification wrapper for model output, not an execution interceptor. A LangChain tool invoked elsewhere is outside this gate; route any supported write through `ProductOrchestrator`. |
| n8n/MCP/UI or other external hosts | External systems remain outside the security boundary. Their tool calls are covered only when the host routes them through the supported product entry point and preserves authenticated host classification. |

These exclusions are intentional, not proof that the excluded routes are safe.
They also do not establish who holds or isolates provider credentials; that is
a separate product requirement.
