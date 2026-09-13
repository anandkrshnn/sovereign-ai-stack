# ADR-006: Evidence-Carrying Orchestration Boundary

## Status

Accepted for the 0.3 product foundation.

## Decision

The Sovereign AI Stack remains a local/offline trust plane. A versioned Python
SDK owns typed agent/task/run/step/tool/policy/verification/evidence contracts
and a deterministic runner. It does not embed n8n, an MCP server, a browser,
or a UI. Providers are injected through adapters and are not security
boundaries.

Each tool call follows: policy decision -> optional approval pause -> bounded
adapter execution with idempotency and retry limits -> semantic verification ->
evidence recording. There are no uncontrolled autonomous loops. Cancellation,
failure, and compensation are explicit run states.

## Consequences

Generated applications can use the contracts without adopting the local
runner. n8n remains an external business workflow engine; Replit, Emergent,
Bolt, and Claude Work remain external product/build surfaces. Production
trust still requires TPM 2.0/HSM; simulator mode is for non-production tests.
