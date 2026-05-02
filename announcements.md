# Sovereign AI Stack — Public Announcements

> **Note**: This file contains announcement copy for social/community channels.
> All copy reflects the current `v0.1.0-preview` framing as of 2026-05-02.
> Do not use the v1 / GA / enterprise-certified language from earlier drafts.

---

## 1. HackerNews (Show HN)

**Title:** Show HN: Sovereign AI Stack – local-first RAG with policy gating and audit logging (alpha)

**Body:**

Hi HN,

I'm sharing an early alpha of the **Sovereign AI Stack** — a personal R&D project
to build a local-first RAG pipeline where every step (retrieval, access control,
response logging) is policy-gated and audit-friendly. No cloud, no telemetry.

**What's implemented and running today:**
- Hybrid retrieval: SQLite FTS5 + LanceDB, fused via a BGE reranker
- ABAC policy gateway: role-based access control before any retrieval runs
- SHA-256-linked audit log, inspectable locally with one CLI command
- OpenAI-compatible bridge (`/v1/chat/completions`) for local model drop-in
- Docker: `docker-compose up` single-command deployment

**What's explicitly not done yet (in the roadmap):**
- A real grounding judge — currently the "verification" is a reranker score proxy,
  not a trained NLI classifier
- Cryptographically signed audit chains — hashing is there, signing is not
- Hardware attestation — references to TPM/Secure Enclave are roadmap items

I'm sharing now because the retrieval + gating scaffold is useful as-is, and I
think honest "here's where I am" posts are more valuable than GA launch announcements.

The IETF draft on PTV Agent Identity
(draft-anandakrishnan-rats-ptv-agent-identity-00) is the conceptual framework
I'm building toward. The code is the first concrete step.

Would love feedback on the retrieval architecture and the audit logging approach.

**GitHub**: https://github.com/anandkrshnn/sovereign-ai-stack
**Install**: `pip install sovereign-ai-stack`

---

## 2. LinkedIn

**Headline:** Building a local-first AI governance scaffold — and being honest about what's done

**Body:**

A few weeks ago I published the first public release of the Sovereign AI Stack.

The pitch I originally made: a fully verified, cryptographically sealed,
enterprise-grade AI control plane. 100% offline. HIPAA-ready.

The honest version: it's a solid scaffold with real retrieval and gating logic —
and several of the bigger claims were roadmap items presented as shipped features.

So I've reframed the project.

**What actually works today:**

✅ Hybrid local RAG — SQLite FTS5 + LanceDB vector store, fused via a BGE reranker.
   Fast, private, no cloud index.

✅ ABAC policy gateway — identity-aware rules gate what each principal can retrieve
   before any query runs.

✅ Audit logging — every step is recorded in an append-only SHA-256-linked chain
   you can inspect locally with one CLI command.

✅ OpenAI-compatible bridge — drop it in front of any local model.

**What I'm still building (explicit roadmap):**

🔧 May 2026: Reproducible benchmark script with hardware and dataset methodology
🔧 June 2026: Real grounding judge with adversarial test suite
🔧 July 2026: Cryptographically signed audit chain
🔧 Q3 2026: Hardware attestation (TPM / Secure Enclave, platform-specific)

The IETF draft I submitted (PTV Agent Identity) is the architectural vision.
The repo is the first concrete implementation step.

If you're exploring local AI pipelines for privacy-sensitive workloads,
the scaffold might be useful — with the explicit caveat that it's a reference
implementation and alpha preview, not a production-certified control plane.

Building it in the open.

🔗 GitHub: https://github.com/anandkrshnn/sovereign-ai-stack
📜 IETF Draft: https://www.ietf.org/archive/id/draft-anandakrishnan-rats-ptv-agent-identity-00.html

#LocalAI #OpenSource #AIGovernance #BuildingInPublic #RAG

---

## 3. Reddit (r/LocalLLaMA)

**Title:** [Project] Sovereign AI Stack – local RAG + ABAC policy gating + audit logging (alpha, honest about what's done)

**Body:**

Hey everyone,

Sharing an early alpha of a stack I've been building: local-first RAG with
policy gating and an audit-friendly logging layer. No cloud, no telemetry.

**Tech stack:**
- Python (FastAPI / Pydantic / Click)
- SQLite FTS5 + LanceDB for hybrid retrieval
- BAAI/bge-reranker-base for fusion
- JSONL + SQLite for audit logging

**What works:**
- Retrieval pipeline runs locally end-to-end
- ABAC gateway: `--principal doctor` restricts retrieval to authorized data
- Audit log: every step SHA-256-linked, inspectable with `sovereign audit verify`
- OpenAI-compatible bridge for local model drop-in

**What's explicitly not done yet:**
- Grounding judge is currently a reranker score threshold, not a real NLI classifier.
  I call this out in the README — don't rely on it for production hallucination detection.
- Audit chain hashing is implemented, signing is not.
- Hardware attestation (TPM / Secure Enclave) is a roadmap item, not shipped.
- Benchmark methodology is being formalized — current numbers are laptop-only.

The IETF draft on PTV Agent Identity is the conceptual direction I'm building toward.

Would appreciate feedback on the retrieval architecture, the ABAC design,
and the audit log format before I go deeper on the grounding judge.

GitHub: https://github.com/anandkrshnn/sovereign-ai-stack

---

## 4. Twitter / X

**Tweet 1:**
Building a local-first RAG + policy-gating scaffold in the open.

What works today: hybrid retrieval, ABAC gating, SHA-256 audit logging, OpenAI bridge.

What's still roadmap: real grounding judge, signed audit chain, hardware attestation.

Honest alpha. 🧵

**Tweet 2:**
The retrieval stack:
- SQLite FTS5 (lexical) + LanceDB (vector)
- Fused via BAAI/bge-reranker-base
- ABAC role check before any retrieval runs
- Every step logged to an append-only chain

100% local. No cloud. No telemetry.

**Tweet 3:**
What I'm not claiming:
❌ "enterprise-certified"
❌ "cryptographically blocking" hallucinations (that's the roadmap)
❌ hardware TPM attestation (also roadmap)

What I am: one engineer, building in public, calling out what's missing.

**Tweet 4:**
Roadmap milestones with "done when" criteria, not just feature bullets:
- May: reproducible benchmark script
- June: real grounding judge + adversarial tests
- July: signed audit chain
- Q3: hardware attestation

GitHub: https://github.com/anandkrshnn/sovereign-ai-stack
IETF: draft-anandakrishnan-rats-ptv-agent-identity-00

#LocalAI #BuildingInPublic
