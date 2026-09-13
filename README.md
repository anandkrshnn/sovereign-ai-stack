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
python verify.py path/to/evidence.json
```

*Note: Demo applications and UI wrappers have been removed to focus on core verification primitives. Integrate `SovereignPipeline` directly via Python or use the CLI.*

## Repository Status
- Focused on the frozen Tamil Nadu case-file update vertical slice (one case-file update path + portable envelope + independent verifier).
- The sprawling agent orchestration module has been entirely deleted; external tools (n8n, MCP hosts, UI builders) remain external integrations, not security boundaries.
- CI blocks merges on formatting, typing, tests, dependency, SAST, secret, and filesystem scan failures.
- Release artifacts are built from tagged commits; hardware-dependent validation remains separate from simulator tests (OPA, Ollama, n8n, and TPM hardware validation are not claimed as validated here).

Keep [LIMITATIONS.md](LIMITATIONS.md) prominent when evaluating this research preview.

## Product boundary

Sovereign AI Stack is the trust and evidence plane. n8n remains external
business workflow automation; Replit, Emergent, and Bolt remain external
product/admin shells; Claude Work remains an external coding and review
surface. None of those tools is treated as a security boundary.

This release does not embed a frontend or autonomous loop. It provides one
regulated case-file update path, portable Ed25519 evidence envelopes, and an
independent replay verifier.
