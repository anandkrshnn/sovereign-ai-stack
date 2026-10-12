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

## Trust-boundary hardening and compatibility

The public `Policy.decide(task, tool_call)` hook is preserved. The runner calls
`Policy.decide_step(task, step)` so host-assigned consequences cannot silently
default to read. Hosts MUST construct `Step.consequence` from trusted metadata,
not accept it from a client. `AllowListPolicy(..., tool_consequences={...})`
can pin tool classifications; standalone `decide` calls deny missing metadata.
Legacy caller `"write"`/`"destructive"` hints can only strengthen a gate.
Allow-list decisions use policy version `"2"` and expose the resolved
`consequence`, which is included in approval and idempotency binding.

Approval records carry a digest over tenant, agent/task/run/step IDs, exact tool
call (excluding mutable state), host consequence, and policy decision/version.
They expire after five minutes by default (configurable up to one hour).
Changed or expired approved requests fail closed. The host authenticates the
principal before calling `approve`; the SDK does not implement an identity
provider or independently signed human approvals.

Idempotency is scoped by `(tenant_id, tool_name, idempotency_key)` and stores an
input/consequence digest. Conflicting reuse fails; identical completed requests
reuse copies of the result. In-flight/ambiguous requests remain reserved.
These reservations are memory-only. A durable host ledger and remote
deduplication/reconciliation are still required across process restarts.

Timeouts, generic `AdapterError`, and unclassified adapter exceptions produce
`RunState.OUTCOME_UNKNOWN` / `ToolCallState.OUTCOME_UNKNOWN`, emit
`tool.outcome_unknown`, and do not retry or issue success evidence. Hosts must
persist these emitted events; the existing success-evidence callback is not an
unknown-outcome ledger. Only `RetryableAdapterError` authorizes bounded retries:
the adapter must guarantee that its failed attempt caused no effect.

Portable case-file verification additionally requires an out-of-band registry:

```python
report = verify_envelope(
    envelope,
    expected_nonce=challenge,
    trusted_signers={"tenant-a": registered_public_keys},
    expected_tenant_id="tenant-a",
)
```

Registered keys are base64-encoded raw Ed25519 public keys, provisioned
independently from the evidence. Missing trust fails closed. V2 envelopes bind
tenant, policy version, request, nonce/run, and approval digests. V1 is rejected.
An unknown execution has `executed=None`; never coerce it into non-execution.
Verified historical evidence is not an anti-replay execution ledger: hosts
must track consumed challenges/runs separately.
