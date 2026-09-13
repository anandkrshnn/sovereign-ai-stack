# Sovereign AI Stack (v0.2.0-alpha1)

**Alpha research prototype** exploring local-first AI verification building blocks.

> [!WARNING]
> This is an **early research preview**. Significant limitations exist. 
> It is **not production-ready**. See [LIMITATIONS.md](LIMITATIONS.md).

Production deployments must provide a TPM 2.0 or HSM-backed anchor. The
software simulator is available only for development and test environments and
must be explicitly enabled with `SOVEREIGN_ALLOW_SIMULATOR=1`.

## Core Components
- **NLI Grounding Gate** — Local DeBERTa-v3 cross-encoder for checking entailment between context and generated responses.
- **Tamper-Evident Audit Chain** — Append-only JSONL with Ed25519 signatures and Merkle roots.
- **TPM 2.0 Anchoring** — Hardware attestation binding on Linux; simulator use is explicit and non-production only.
- **LangChainGuard** — Basic wrapper for adding verification to LangChain/LCEL pipelines.
- **Evidence-Carrying Orchestrator** — Versioned agent/task/run contracts, deterministic tool execution, policy and approval gates, and evidence bundles for external builders. See [the integration contract](docs/INTEGRATION_CONTRACT.md).

## Quickstart

```bash
git clone https://github.com/anandkrshnn/sovereign-ai-stack.git
cd sovereign-ai-stack

# Install minimal core without bloat
pip install -e .[verify]

# Use the sovereign CLI
sovereign --help
```

*Note: Demo applications and UI wrappers have been removed to focus on core verification primitives. Integrate `SovereignPipeline` directly via Python or use the CLI.*

## Repository Status
- Focused on verification primitives only.
- The orchestration foundation is intentionally local, deterministic, and provider-neutral; n8n, MCP hosts, and UI builders remain external integrations.
- The sprawling agent orchestration module has been entirely deleted.
- CI blocks merges on formatting, typing, tests, dependency, SAST, secret, and filesystem scan failures.
- Release artifacts are built from tagged commits; hardware-dependent validation remains separate from simulator tests.

Contributions welcome, especially around hardening, testing, and documentation of failure modes.

## Product boundary

Sovereign AI Stack is the trust and evidence plane. n8n remains external
business workflow automation; Replit, Emergent, and Bolt remain external
product/admin shells; Claude Work remains an external coding and review
surface. None of those tools is treated as a security boundary.

The 0.3 orchestration foundation does not embed a frontend or autonomous loop.
Use the typed SDK contracts and adapter interfaces to submit bounded tasks,
stream status events, handle explicit approvals, and verify signed audit
evidence.
