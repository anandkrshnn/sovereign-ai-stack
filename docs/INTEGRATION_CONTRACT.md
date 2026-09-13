# Orchestrator integration contract (v1)

External builders call the local SDK or a host-provided API facade. The
canonical objects are `Agent`, `Task`, `Run`, `Step`, `ToolCall`,
`PolicyDecision`, `VerificationResult`, `EvidenceBundle`, `Approval`, and
`ArtifactRef` in `sovereign_ai.orchestration`.

1. Submit a task with `tenant_id`, `agent_id`, an idempotency key, and bounded
   input. The host creates a run and returns its stable ID.
2. Subscribe to emitted `run.*`, `step.*`, `tool.*`, `policy.*`,
   `approval.*`, and `verification.*` events. Events are append-only facts and
   include run/step IDs.
3. When a run is `waiting_approval`, display the requested consequence and call
   the host approval operation with an authenticated principal. Approval is
   explicit; clients must not infer it from a timeout.
4. Fetch the evidence bundle after each successful step. Verify its hashes and
   the signed audit record before treating output as trusted.

## n8n example

An n8n workflow may POST a task to a host facade and use a webhook callback for
status events. The webhook is an integration transport, not a security
boundary. The host must validate tenant identity, enforce idempotency, apply
policy, and retain Sovereign evidence. n8n credentials and business actions
remain outside this repository.

MCP, HTTP, and CLI adapters follow the same contract: bounded arguments,
declared timeout, explicit policy decision, deterministic result serialization,
and evidence after verification.
