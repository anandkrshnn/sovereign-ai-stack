# Sovereign AI Stack (v0.2.0-alpha)

**Alpha research prototype** exploring local-first AI verification building blocks.

> [!WARNING]
> This is an **early research preview**. Significant limitations exist. 
> It is **not production-ready**. See [LIMITATIONS.md](LIMITATIONS.md).

## Core Components
- **NLI Grounding Gate** — Local DeBERTa-v3 cross-encoder for checking entailment between context and generated responses.
- **Tamper-Evident Audit Chain** — Append-only JSONL with Ed25519 signatures and Merkle roots.
- **TPM 2.0 Anchoring** — Hardware (or simulator) attestation binding on Linux.
- **LangChainGuard** — Basic wrapper for adding verification to LangChain/LCEL pipelines.

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
- The sprawling agent orchestration module has been entirely deleted.
- CI is configured for linting, basic tests, and container scanning.

Contributions welcome, especially around hardening, testing, and documentation of failure modes.
