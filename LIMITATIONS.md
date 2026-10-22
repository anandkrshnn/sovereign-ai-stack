# LIMITATIONS: Sovereign AI Stack (v2.0)

## Experimental tool-write admission and local execution journal

For the experimental generic adapter runner, the product-facing
`ProductOrchestrator` requires an explicit trusted consequence for every
allowlisted tool. It refuses construction if any configured write or
destructive tool lacks a journal. At dispatch it also denies a write step
without a journal before invoking its adapter. Read-only tool configurations
may omit the journal.

The journal is a first, single-host POSIX recovery slice. `DeterministicOrchestrator`
retains its in-memory behavior for low-level compatibility and is not supported
for product writes. The explicit `VolatileOrchestrator` is test/development
only, emits a warning, and cannot be selected through `ProductOrchestrator`.
Legacy low-level construction without a journal emits a warning as well.

The supported configuration is scoped only to writes executed through
`ProductOrchestrator` with `SQLiteExecutionJournal` and a supported
attempt-bound adapter. It is not a general write interceptor, credential
broker, or protection against code that bypasses this entry point. See
[`docs/WRITE_ADMISSION.md`](docs/WRITE_ADMISSION.md) for the route inventory
and explicit exclusions.

It requires one active journal owner, an exclusive OS process lock, a trusted
local filesystem, and SQLite WAL/FULL read-back. It preserves interrupted
in-flight work as unknown and does not redispatch it. Reserved-only recovery is
distinct from ambiguous execution and still requires the owner-generation
dispatch barrier. Do not use hard-link aliases, delete/replace the active
database or lock file, or deploy it on a network/shared filesystem.
Journal objects/connections must not be inherited for use by forked children;
process-identity checks reject that use before touching a transaction or lock.

This slice does not implement distributed failover/fencing, reconciliation,
attempt-bound no-effect retries, a late-evidence reducer, durable approval
storage, exactly-once delivery, or automatic resolution of unknown outcomes.
No real-provider capability or hardware/power-loss guarantee is established
by the local process-kill fixture.

The host must provide an attempt-aware adapter and authenticate principals;
host-local binding metadata and unkeyed content digests are not independent
trust roots. The process lock coordinates cooperating journal owners, not a
host administrator or arbitrary direct database writers. External evidence-hook
delivery is not atomic with the terminal journal commit. Semantic task rejection
does not prove a confirmed remote write had no effect.

## Write-admission route boundary

This gate does not cover the separate Tamil Nadu evidence workflow and its
optional direct webhook callback, arbitrary direct adapter calls, local
vector-store ingestion, or tools invoked directly by an external host. Those
paths are either non-durable simulators/verification flows or explicitly
unsupported for durable product writes. The LangChain guard verifies model
output; it does not intercept tools executed outside this runner. None of these
statements claims that remote credentials are held outside an agent or host.

## Technical Limitations of the NLI Gate

The Natural Language Inference (NLI) Gate relies on a cross-encoder model to verify text. It is a probabilistic filter, not a deterministic rule engine. The following are fundamental architectural limitations:

### 1. Syntactic Mimicry
The gate correlates structural similarity with entailment. If a hallucinated response closely mimics the noun phrases and syntax of the source context, the model typically approves it with high confidence (>90%). It relies on pattern matching rather than formal logic reasoning.

### 2. Numerical and Entity Blindness
In contexts with dense terminology (e.g., financial documents or medical records), the cross-encoder frequently fails to identify swapped numbers or entities. A generated answer altering "$400M" to "$40M" may pass if the surrounding boilerplate is identical. Secondary exact-match verification (like regex or named entity extraction) is strictly required for quantitative data.

### 3. Multi-Hop Logical Negation
The model struggles to correctly process nested logical negations (e.g., "It is not the case that X is absent"). Such constructs cause embedding distortion, leading to unreliable confidence scores that bypass standard rejection thresholds.

### 4. Out-of-Distribution Vulnerability
The underlying model (DeBERTa v3) is trained on standard NLI datasets (SNLI/MultiNLI). It lacks domain-specific vocabularies. When evaluating complex cryptographic specifications or proprietary biochemical research, confidence scores hold minimal predictive value.

### 5. Context Truncation
Input arrays (`query + context + answer`) exceeding 512 tokens are silently truncated. If critical grounding information resides at the end of the context, the gate may incorrectly reject a faithful answer or approve an ungrounded one based on incomplete data.

### Deployment Requirement
The NLI Gate cannot operate as a standalone security boundary. It must be paired with strict confidence thresholding (>= 0.85), exact-match safety nets, and human oversight for high-risk deployments.

## Technical Limitations of the Audit Chain

The forensic audit chain provides tamper-evident append-only logging using cryptographic hashes, Ed25519 signatures, and Merkle Trees. The following are fundamental architectural limitations:

### 1. Proof Availability Delay
The `get_audit_proof(audit_id)` function relies on a block being sealed into a `MERKLE_CHECKPOINT`. Until the configured checkpoint interval (e.g., 10 events) is reached, recent events cannot yield a valid Merkle root or hardware attestation quote.

### 2. State Rollback Attacks
While tampering with an existing record breaks the hash chain and Merkle inclusion proofs, an attacker with root access to the filesystem could delete the entire audit log or roll it back to a previous valid state. Prevention of rollback attacks relies entirely on out-of-band monitoring or remote replication of checkpoints.

### 3. Key Compromise
The integrity of the chain relies on the hardware anchor (TPM/HSM) or the software signing key. If the underlying host environment is severely compromised such that the signing key is extracted or arbitrary payloads can be injected into the signing module, the attacker can forge a mathematically valid alternate history.

### 4. Exclusion Proofs
The current implementation supports standard inclusion proofs but does not feature sorted Sparse Merkle Trees. Exclusion (proving a specific event did not occur) is handled by linear search and raising an exception if absent, rather than via O(log N) cryptographic non-inclusion proofs.
