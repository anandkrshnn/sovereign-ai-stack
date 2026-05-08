# ADR 003: Merkle Tree Audit Aggregation

## Status
Accepted (v0.1.0a2)

## Context
Linear hash chains (`Hash(n-1) -> Hash(n)`) are sufficient for basic tamper-evidence but inefficient for large-scale auditing. Verifying a single event requires the auditor to re-hash the entire preceding chain (O(n)). In multi-tenant environments, we need a way to prove that an event exists in a specific history without sharing the entire sensitive log.

## Decision
We will transition from linear chaining to **Merkle Tree Aggregation** for forensic audit events.

## Rationale
- **Efficiency**: Verification of an event's inclusion in a history becomes **O(log n)** rather than O(n).
- **Privacy**: We can provide a **Merkle Proof** to a third-party auditor that a specific "Airlock Failure" occurred without revealing the content of other private user queries.
- **Root Anchoring**: Only the Merkle Root needs to be signed by the Hardware Anchor (TPM) or published to a public beacon to secure the entire batch of logs.

## Consequences
- **Batching**: Audit records must now be managed in "epochs" or batches to calculate tree roots.
- **Complexity**: Verification logic is more complex, requiring a Merkle Proof verification library.
- **Forensic API**: The `AuditChain` API must be extended to support `get_inclusion_proof(event_id)`.
