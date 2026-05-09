# Sovereign AI Stack (Reference Implementation)

**A Technical Framework for Local-First RAG Verification and Forensic Auditability**

> [!CAUTION]
> **Experimental Research Preview (v0.1.0a4)**
> This repository is a reference implementation for technical exploration. It is **not** currently certified for production use with sensitive data. Last architecture audit: May 2026.

---

## 🔬 Overview

The **Sovereign AI Stack** is an experimental reference implementation for local-first AI governance. It explores a **Verify-First** architecture using **NLI-based Grounding Checks** and **Signed Forensic Audit Trails** to mitigate hallucination and tampering risks in regulated environments.

---

## 🏗️ Technical Architecture

The stack operates as an experimental **Verify-First** pipeline.

```mermaid
flowchart TD
    A["User Query + Principal"] --> B["Hybrid Retriever<br/>BM25 + Dense"]
    B --> C["Context Builder"]
    C --> D["NLI Grounding Gate<br/>DeBERTa-v3<br/>≥0.85 entailment"]
    D -->|Pass| E["LLM Generation<br/>with Citations"]
    D -->|Fail| F["Verification Failure<br/>Insufficient Grounding"]
    E --> G["Signed Audit Event<br/>Ed25519 Chain"]
    F --> G
    G --> H["Merkle Aggregation<br/>(10-event blocks)"]
    H --> I["Hardware Attestation Quote<br/>TPM 2.0 / IETF RATS"]
    I --> J["Forensic Certificate"]
```

Detailed architecture documentation, including C4 Container Diagrams and Architecture Decision Records (ADRs), can be found in [docs/architecture/c4-container-v0.1.0a4.md](docs/architecture/c4-container-v0.1.0a4.md).

For an honest assessment of current technical debt and discrepancies, see [docs/architecture/KNOWN_GAPS.md](docs/architecture/KNOWN_GAPS.md).

---

## ✨ Key Features (Alpha)

- **NLI Grounding Gate (Experimental)**: Uses a local cross-encoder (`DeBERTa-v3`) to score logical entailment between context and LLM claims. This is a heuristic verification layer, not a formal proof.
- **Hardware-Attested Forensics (Alpha)**: Every decision event is signed and aggregated into Merkle Trees, with roots bound to **TPM 2.0 Hardware Quotes** (IETF RATS compliant).
- **ABAC Policy Engine**: Attribute-Based Access Control filters context *before* generation.
- **Compatibility Layer**: Basic OpenAI-compatible gateway via the `sovereign-ai-bridge`.

---

## 🔒 Transparency & Trust Boundaries

| Feature | Research Implementation | Production Hardening Status |
| :--- | :--- | :--- |
| **Grounding** | NLI threshold (DeBERTa-v3) | Experimental |
| **Forensics** | TPM 2.0 / IETF RATS (Linux Native) | Alpha |
| **Isolation** | Logical (Filesystem + SQL) | Prototype |

> [!IMPORTANT]
> **Hardware-Anchored Trust**: v0.1.0a4 introduces the **Hardware Abstraction Layer (HAL)**. It supports native **TPM 2.0 (ESYS)** on Linux for remote attestation, with structural support for Windows and a high-fidelity simulator for development.

---

## 🛡️ Hardware-Attested Audit Chain (v0.1.0a4)

The Sovereign AI Stack provides a non-repudiable forensic trail by binding software-level audit events to hardware-level measurements.

- **Merkle Checkpoints**: Audit events are aggregated into Merkle Trees. Every 10 events (or on shutdown), a `MERKLE_CHECKPOINT` is generated.
- **Hardware Binding**: The Merkle Root of the block acts as a **nonce** for a TPM 2.0 Quote.
- **PCR measurements**: The quote includes platform measurements (PCR 0 for firmware, PCR 11 for application state), proving that the audit log was generated on specific, untampered hardware.
- **IETF RATS Compliance**: Evidence bundles follow the **Remote ATtestation procedureS (RATS)** architecture, enabling remote verification of node integrity.

---

## 🛡️ NLI Verification in Action (Conceptual)

The "Airlock" uses a local NLI model to check grounding logic.

```mermaid
sequenceDiagram
    participant L as LLM (Draft)
    participant V as NLI Gate (Alpha)
    participant U as User

    L->>V: "The patient's heart rate is 72 bpm."
    Note over V: "Context: BP 120/80. Resting."
    V-->>V: "Logic: Contradiction/Neutral"
    V->>U: "ALERT: Grounding Failure"
```

---

## 🚀 Quick Start

### 1. Install via Pip
```bash
pip install sovereign-ai-stack
```

### 2. Run the Gateway (OpenAI Compatible)
```bash
python -m sovereign_ai.bridge.main
```

### 3. Explore Examples (Research Preview)
We provide three end-to-end examples in the [examples/](examples/) directory:

| Example | What it demonstrates | Status |
| :--- | :--- | :--- |
| [`01_basic_rag.py`](examples/01_basic_rag.py) | Minimal RAG setup | Stable |
| [`02_verified_query.py`](examples/02_verified_query.py) | NLI Grounding Gate | Experimental |
| [`03_forensic_agent.py`](examples/03_forensic_agent.py) | Signed Audit Chains | Alpha |

---

## 📈 Technical Benchmarks (Alpha)

*Hardware: MacBook Pro M2 Max (32GB) | Model: Qwen-2.5-7B-Instruct (Ollama)*
*Note: These numbers are baseline results and have not yet been validated across diverse hardware or scaled datasets.*

| Operation | Latency (P50) | Verification Rate |
|---|---|---|
| Vector Retrieval | 12ms | N/A |
| Policy Evaluation | 4ms | 100% |
| **NLI Verification (Airlock)** | **82ms** | **~94% (Med-QA Subset)** |
| Cryptographic Signing | 1ms | 100% |

---

## ⚠️ Known Limitations

- **NLI Thresholding**: The default 0.8 threshold may produce false negatives in highly creative writing tasks; it is tuned for *fact-based retrieval*.
- **Hardware Binding**: Support for **TPM 2.0** is now live via the pluggable HAL. Native ESYS support is available for Linux; Windows and macOS fall back to software-bound simulator keys unless configured otherwise.
- **Context Window**: Verification latency scales linearly with the number of claims; massive responses (>2048 tokens) may see a lag.

---

## 🛡️ Security Model & Threat Considerations

- **Trust Assumptions**: We assume the host OS (Linux/Windows/macOS) is not compromised at the kernel level.
- **Out of Scope**: This stack does not protect against physical side-channel attacks on the CPU/RAM (yet).
- **Fail-Closed**: If the verification model fails to load or the signature chain is broken, the system **blocks** all output.

---

## 🗺️ Target Maturation Roadmap

For detailed technical requirements to reach production readiness, see [Maturation Gates](docs/architecture/MATURATION_GATES.md).

- **Phase 1 (Completed)**: Monorepo consolidation, Forensic Hardening (Merkle/STRIDE), Remote Trust Preview (RATS), Pluggable Hardware Abstraction Layer (HAL).
- **Phase 2 (Completed)**: Hardware-Anchored Merkle Checkpoints, Linux TPM 2.0 Native Integration (ESYS).
- **Phase 3 (2026/2027)**: Secure Enclaves (Intel SGX), ZK-Proofs for compliance, Knowledge-Augmented Gates (K-Gate).

---

## 🤝 Contributing

We value "Brutal Feedback". Please report any architectural bypasses or cryptographic flaws in the Issues section.

---

## 📜 License
MIT
