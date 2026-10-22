# Sovereign AI Stack (v0.3.0a1)

**Alpha research preview** exploring local-first AI verification building blocks.

> [!WARNING]
> **Research preview only. Not production-ready.** See [LIMITATIONS.md](LIMITATIONS.md).

**Frozen scope:** Block and prove high-impact agent tool calls in one regulated
Tamil Nadu workflow, with independently replayable evidence.

Production deployments must provide a TPM 2.0 or HSM-backed anchor. The
software simulator is available only for development and test environments and
must be explicitly enabled with `SOVEREIGN_ALLOW_SIMULATOR=1`.

## Core Components
- **NLI Grounding Gate** — Local DeBERTa-v3 cross-encoder for checking entailment between context and generated responses.
- **Tamper-Evident Audit Chain** — Append-only JSONL with Ed25519 signatures and Merkle roots.
- **TPM 2.0 Anchoring** — Hardware attestation binding on Linux; simulator use is explicit and non-production only.
- **LangChainGuard** — Basic wrapper for adding verification to LangChain/LCEL pipelines.
- **Case-File Evidence Slice** — One deterministic case-file update path, portable Ed25519 evidence envelope, and independent verifier for regulated tool calls.

## Clean-machine verification

```bash
git clone https://github.com/anandkrshnn/sovereign-ai-stack.git
cd sovereign-ai-stack

# Create an isolated environment and install the project
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
python -m pip install -e .

# Run the deterministic workflow and standalone evidence verifier
python -m pytest -q tests/workflows/test_tamilnadu_seva.py
python verify.py path/to/evidence.json --trusted-keys trusted-signers.json --tenant default
```

*Note: Demo applications and UI wrappers have been removed to focus on core verification primitives. Integrate `SovereignPipeline` directly via Python or use the CLI.*

## Repository Status
- Focused on the frozen Tamil Nadu case-file update vertical slice (one case-file update path + portable envelope + independent verifier).
- The Tamil Nadu case-file workflow is separate from the experimental `sovereign_ai.orchestration` adapter runner; neither workflow envelopes nor external hosts such as n8n/MCP provide a write-security boundary by themselves.
- CI blocks merges on formatting, typing, tests, dependency, SAST, secret, and filesystem scan failures.
- Release artifacts are built from tagged commits; hardware-dependent validation remains separate from simulator tests (OPA, Ollama, n8n, and TPM hardware validation are not claimed as validated here).

Keep [LIMITATIONS.md](LIMITATIONS.md) prominent when evaluating this research preview.

## Experimental tool-write admission

For the experimental adapter runner, use `ProductOrchestrator`. It requires an
explicit trusted consequence for every allowlisted tool and a
`SQLiteExecutionJournal` for any configured write or destructive tool. A
read-only product configuration can omit the journal; a step that escalates to
a write is still rejected before adapter dispatch. See
[the write-admission route inventory](docs/WRITE_ADMISSION.md).

`DeterministicOrchestrator` remains a low-level compatibility API and its
in-memory mode is not supported for product writes. `VolatileOrchestrator` is
an explicit, warning-emitting test/development option, not a product
configuration. This single-host write-admission boundary does not make the
Tamil Nadu workflow, direct adapter calls, external hosts, or other database
writes durable, and does not address who holds remote credentials.

## Trust-boundary contract

Portable envelopes now use `tn-seva.case-file.v2`: tenant, policy version, exact
request digest, approval binding, and three-valued execution (`true`, `false`,
or `null` for unknown) are signed. V1 envelopes are rejected; regenerate them
rather than inferring missing authorization scope.

Verifier keys must come from an independently provisioned tenant registry,
never from the evidence being checked. See
[the workflow guide](docs/TAMILNADU_SEVA_WORKFLOW.md) for the development-only
CLI and [the SDK contract](docs/INTEGRATION_CONTRACT.md) for compatibility changes.

These safeguards are in-process, not restart-safe exactly-once delivery. Human
identity authentication belongs to the host; a runtime-signed principal string
is not an independent operator signature. Production principal authentication,
durable execution/reconciliation, and TPM/HSM validation remain prerequisites.

## Product boundary

Sovereign AI Stack is the trust and evidence plane. n8n remains external
business workflow automation; Replit, Emergent, and Bolt remain external
product/admin shells; Claude Work remains an external coding and review
surface. None of those tools is treated as a security boundary.

This release does not embed a frontend or autonomous loop. It provides one
regulated case-file update path, portable Ed25519 evidence envelopes, and an
independent replay verifier.
