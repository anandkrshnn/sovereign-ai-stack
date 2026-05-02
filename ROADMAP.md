# 🗺️ Sovereign AI Stack — Roadmap

> **Current release**: `v0.1.0-preview` (alpha) — a reference implementation.
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

**Known gaps at this release (now explicit):**
- Grounding judge is a reranker score threshold, not a trained classifier
- Audit chain is hashed, not signed — no non-repudiation yet
- No hardware attestation beyond Python `keyring` credential storage
- No external compliance certification

---

## 🔧 v0.2.0 — Target: May 2026

**Scope: Reproducible benchmarks + honest baselines.**

- [ ] `benchmark.py`: reproducible latency/throughput script that prints hardware,
      dataset size, model, and runtime settings — runnable by anyone
- [ ] Methodology note added to README with hardware spec and corpus description
- [ ] Remove any remaining performance claims from docs that lack a linked script
- [ ] Add `pytest -m benchmark` integration so CI captures regression data

**Done when**: `python benchmark.py` runs end-to-end on a clean checkout and
produces a results file that a third party can reproduce on similar hardware.

---

## 🔬 v0.3.0 — Target: June 2026

**Scope: Real grounding judge with adversarial test coverage.**

- [ ] Integrate a local NLI model (`cross-encoder/nli-deberta-v3-small` or equiv.)
      as a genuine grounding classifier — not just reranker score threshold
- [ ] Add adversarial test suite: deliberately hallucinated answers must be blocked
      (not just logged) before the grounding gate passes them
- [ ] Publish grounding accuracy methodology with test corpus and pass/fail criteria
- [ ] Update capability table: "Grounding Judge" moves from 🔧 Roadmap to ✅ Implemented

**Done when**: `pytest tests/adversarial/` passes with a documented failure injection
set, and the README accuracy claim links to the test script and corpus.

---

## 🔐 v0.4.0 — Target: July 2026

**Scope: Cryptographically signed audit chain.**

- [ ] Each log entry signed with Ed25519 (using `cryptography` library)
- [ ] Chain verification: `sovereign audit verify` checks signature continuity,
      not just hash continuity
- [ ] Adversarial test: tampered log entry detected and rejected by verifier
- [ ] Update capability table: "Signed Audit Chain" moves from 🔧 Roadmap to ✅ Implemented

**Done when**: `sovereign audit verify` returns a non-zero exit code on a tampered
log, and the signing key derivation is documented in `docs/SECURITY.md`.

---

## 🔩 v0.5.0 — Target: Q3 2026 (date TBD)

**Scope: Real hardware attestation (platform-specific).**

- [ ] Linux: `tpm2-tools` integration for TPM2 PCR binding
- [ ] macOS: Secure Enclave via `CryptoKit` or equivalent Python bridge
- [ ] Windows: DPAPI or TPM2 via `tpm2-pytss`
- [ ] Document platform support matrix explicitly — not all platforms will be supported
- [ ] Update capability table: "Hardware Attestation" moves from 🔧 Roadmap to ✅ Implemented

**Note**: This is the hardest milestone. Platform support will be incremental.
The feature will not be claimed until at least one platform has reproducible
attestation with a test that verifies binding survives key rotation.

---

## 📋 External Validation — No date committed

These items require third-party work and cannot be given internal target dates:

- External compliance certification (HIPAA, SOC 2 Type II)
- IETF RATS working group adoption of PTV draft
- Independent security audit of the audit chain implementation

These will be tracked in GitHub Issues as they become active.

---

## What is not on this roadmap

The following items from the original `ROADMAP.md` have been removed because
they were aspirational without a realistic implementation path:

- Remote forensic anchors (Git / IPFS / Blockchain) — too broad for current scope
- Managed Sovereign Cloud / Enterprise Pilot Program — commercial, not OSS
- GAIP-2030 autonomous compliance agents — undefined standard, no implementation path
- Helm charts / K8s — premature until core features are stable

---

*Roadmap updated: 2026-05-02*
*Next review: 2026-06-01*
