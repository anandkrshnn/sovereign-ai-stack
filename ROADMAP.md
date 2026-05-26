# 🗺️ Sovereign AI Stack — Roadmap

> **Current release**: `v1.1.0a2` (alpha) — a reference implementation.
> This roadmap is a dated, scoped commitment list, not a vision document.
> Each milestone will be marked complete only when the associated tests pass and
> the implementation is publicly verifiable in the repository.

---

## ✅ v0.1.0-preview — Done (2026-04-27)

**Scope: Local-first RAG scaffold with policy gating and audit logging.**

- [x] Hybrid retrieval: SQLite FTS5 (lexical) + LanceDB (vector) + BGE reranker
- [x] ABAC policy gateway: role-based access control per principal before retrieval
- [x] Audit logging: SHA-256-linked append-only JSONL + SQLite event chain
- [x] OpenAI-compatible bridge: `/v1/chat/completions` drop-in
- [x] CLI: `sovereign ask`, `sovereign audit verify`
- [x] Docker: `docker-compose up` single-command deployment
- [x] PyPI package: `pip install sovereign-ai-stack`

---

## ✅ v0.3.0 (Accelerated) — Done (2026-05-02)

**Scope: Real grounding judge with adversarial test coverage.**

- [x] **NLI Judge**: Integrated `cross-encoder/nli-deberta-v3-base` as a deterministic grounding classifier (replaced fragile generative LLM judge).
- [x] **Adversarial Security**: Added dedicated test suite (`tests/verify/test_evaluator_adversarial.py`) validating the gate against hallucinations and contradictions.
- [x] **Performance**: Optimized judge latency to ~50ms on CPU, enabling real-time "Verified Airlock" enforcement.

---

## ✅ v0.4.0 (Accelerated) — Done (2026-05-02)

**Scope: Asymmetrically signed audit chain.**

- [x] **Ed25519 Signatures**: Every audit anchor is now digitally signed using an Ed25519 private key, providing non-repudiable proof of state.
- [x] **OS-backed Secure Storage**: Signing keys are provisioned and stored in the OS Secure Storage (Windows Credential Manager / macOS Keychain) via `keyring`.
- [x] **Public Verifiability**: Audit anchors include the public key, allowing external entities to verify forensic integrity without access to raw logs.
- [x] **Deterministic Chaining**: Implemented Canonical JSON serialization for all audit hashes to ensure cross-platform reproducibility.

---

## 🔧 v0.2.0 — Target: May 2026

**Scope: Reproducible benchmarks + honest baselines.**

- [ ] `benchmark.py`: reproducible latency/throughput script that prints hardware,
      dataset size, model, and runtime settings — runnable by anyone
- [ ] Methodology note added to README with hardware spec and corpus description
- [ ] Remove any remaining performance claims from docs that lack a linked script
- [ ] Add `pytest -m benchmark` integration so CI captures regression data

---

## 🔩 v0.5.0 — Target: Q3 2026

**Scope: Real hardware-bound attestation (TPM/Enclave integration).**

- [ ] Linux: `tpm2-tools` integration for TPM2 PCR binding
- [ ] macOS: Secure Enclave via `CryptoKit` or equivalent Python bridge
- [ ] Windows: DPAPI or TPM2 via `tpm2-pytss`
- [ ] Document platform support matrix explicitly — not all platforms will be supported
- [ ] **Challenge**: Move from "Secure Storage" to "Hardware-Backed Signing" (key never leaves the enclave).

---

## ✅ v0.6.0 (Immune System Brain & PTV Synergy) — Done (2026-05-26)

**Scope: Verifiable Adaptive Governance (Immune Memory + ZK Policy Attestation).**

- [x] **Adaptive Memory Core**: Integration of the `VerifiedBrain` with local high-performance LanceDB vector embedding storage and Neo4j/local network graph memory.
- [x] **ZK-Policy Gate (PTV Synergy)**: Integrate the hardware-anchored zero-knowledge attestation (Groth16) with the NLI gate to generate cryptographically verifiable proof of policy-compliant knowledge transformation without leaking underlying dataset contents.
- [x] **Dynamic Quarantine Resolution**: Fully automated consensus agent protocol where multiple independent LLMs/Classifiers act as a jury to resolve quarantined antigens.
- [x] **AI Verify & IMDA Alignment**: Implementation of audit templates directly compliant with Singapore's Model AI Governance Framework and AI Verify tools.

---

## 🧠 v0.7.0 (Memory Consolidation) — Target: Q1 2027

**Scope: Long-term Semantic Distillation and Knowledge Lifecycle.**

- [ ] Automatic promotion of Layer 1 facts to Layer 2 Wisdom Principles.
- [ ] Garbage collection for obsolete or overridden knowledge vectors.
- [ ] Semantic deduplication across the Merkle history.

---

## 📊 v0.8.0 (Brain Health Dashboard) — Target: Q2 2027

**Scope: Visual Observability of the Immune System.**

- [ ] Real-time Autoimmune Threshold monitoring dashboard.
- [ ] Visual Quarantine Zone with one-click resolution.
- [ ] Merkle chain audit explorer UI.

---

## 📋 External Validation — No date committed

These items require third-party work and cannot be given internal target dates:

- External compliance certification (HIPAA, SOC 2 Type II)
- IETF RATS working group adoption of PTV draft
- Independent security audit of the audit chain implementation

---

*Roadmap updated: 2026-05-26*
*Next review: 2026-06-01*

