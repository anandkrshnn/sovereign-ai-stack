---
name: sovereign-ai-architect
description: Core architectural principles and DevSecOps guidelines for the Sovereign AI Stack. Trigger when modifying the pipeline, audit chains, NLI gate, or hardware attestation.
risk: safe
---

# Sovereign AI Stack Architect

Use this skill when developing or auditing the Sovereign AI Stack. The repository enforces an elite standard of verifiable AI, rooted in cryptographic proof and zero-trust engineering.

## 1. Core Philosophy: The Verify-First Airlock

- **No Security Theater**: Prompt-based "self-correction" and API wrappers are not security. Do not rely on them.
- **Fail-Closed Default**: If a condition is ambiguous, halt. If an attestation quote fails, halt. If the NLI gate falls below the 0.85 threshold, reject the payload.
- **Brutal Minimalism**: Do not add over-engineered abstractions. Strip away legacy code and helper layers. Ensure cryptographic operations are O(1) where possible (e.g., Merkle proof verification using indices).

## 2. Component Guidelines

### Audit Ledger (`common/audit.py`, `common/merkle.py`)
- The ledger must remain an append-only JSONL file supported by an `.idx` file for O(1) seeks.
- Merkle proofs must be generated dynamically.
- Do not mix sync and async code (`nest_asyncio` is banned). Use `asyncio.to_thread` for CPU-bound hashing to release the GIL.

### NLI Grounding Gate (`verify/evaluator.py`)
- Inference must be explicitly offloaded to a thread pool via `asyncio.to_thread` to prevent blocking the event loop during heavy cross-encoder matrix multiplications.
- The gate must enforce a strict `0.85` Platt-calibrated threshold.
- Log all failures cleanly to a designated `low_confidence.log`.

### Pipeline Orchestration (`pipeline.py`)
- Enforce explicit async initialization via `await pipeline.initialize()`.
- Do not execute the LLM inference loop until the Hardware Attestation enclave returns a valid quote.

## 3. DevSecOps CI Expectations

All PRs must mathematically prove their safety before merging. When creating or updating features, ensure they pass:
1. **Linting**: `ruff`, `mypy` strict, `black`, `isort`.
2. **SAST**: `bandit` and `semgrep` configured for cryptographic vulnerability scanning.
3. **Fuzzing**: Provide `hypothesis` property-based tests for any new edge case.
4. **Performance**: Do not degrade NLI throughput or cryptographic hashing speeds.

## 4. Documentation Tone

- Maintain a tone of absolute authority, precision, and intellectual honesty.
- Always document scalability gaps and threat model limitations (e.g., in `LIMITATIONS.md` or `docs/architecture.md`).
- Focus on top-tier engineering appeal: Target Principal Engineers, Cryptographers, and Compliance CTOs.

## When to Use
Trigger this skill whenever asked to add features, refactor code, write documentation, or review PRs in the `sovereign-ai-stack` repository.
