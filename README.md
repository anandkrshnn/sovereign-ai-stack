# Sovereign AI Stack

**Local-First RAG with Verifiable Grounding and Forensic Auditability**

> [!CAUTION]
> **Alpha Release (v1.1.0a2) | Research Prototype**
> This repository is for technical exploration and research purposes only. It is **not** currently certified for production use with sensitive data. Last security/architecture audit: May 2026.

---

## 🔬 Overview

The **Sovereign AI Stack** is a reference implementation for high-trust, local-first agentic workflows. It addresses the "Black Box" problem in RAG by enforcing **Deterministic Verification** and **Non-Repudiable Forensics**.

Target Use Cases:
- **Regulated Data Silos**: Healthcare (HIPAA), Finance (SEC/FINRA).
- **Compliance-First Apps**: DPDP (India) and GDPR (EU) compliant retrieval.
- **Critical Infrastructure**: Air-gapped or high-security local environments.

---

## ✨ Key Features (Current Scope)

- **The Verified Airlock**: Every claim in an LLM response is verified using an NLI Cross-Encoder (`DeBERTa-v3`) against the retrieved context.
- **Forensic Audit Chain**: Every decision, retrieval, and verification event is signed with **Ed25519 asymmetric cryptography**.
- **ABAC Policy Engine**: Attribute-Based Access Control filters context *before* generation, preventing data leakage at the source.
- **Multi-Tenant Isolation**: Physical isolation of encrypted SQLite/LanceDB silos per tenant/principal.
- **OpenAI-Compatible Gateway**: Plug-and-play compatibility via the `sovereign-ai-bridge`.

---

## 🏗️ Architecture

The stack operates on a **Fail-Closed, Verify-First** pipeline:

1.  **Retrieve**: Local retrieval from scoped, encrypted silos.
2.  **Govern**: Policy engine filters context using zero-trust principles.
3.  **Generate**: LLM produces a draft response based *only* on governed context.
4.  **Verify**: The Airlock ensures logical entailment (Deterministic Grounding).
5.  **Certify**: The trace is signed and anchored to the OS secure keyring.

---

## 🚀 Quick Start

### 1. Install via Pip
```bash
pip install sovereign-ai-stack
```

### 2. Run the Gateway
```bash
python -m sovereign_ai.bridge.main --model qwen2.5:7b
```

### 3. Verification Example
```python
from sovereign_ai.verify.evaluator import SovereignEvaluator

evaluator = SovereignEvaluator()
result = evaluator.evaluate(
    query="What is the patient's heart rate?",
    context="Observation 10:45 AM: HR 72bpm, BP 120/80.",
    answer="The patient's heart rate is 72 bpm."
)

print(f"Passed Grounding: {result['passed']}") # True
```

---

## 📈 Performance & Benchmarks

*Hardware: MacBook Pro M2 Max (32GB) | Model: Qwen-2.5-7B-Instruct (Ollama)*

| Operation | Latency (P50) | Accuracy (NLI) |
|---|---|---|
| Vector Retrieval | 12ms | N/A |
| Policy Evaluation | 4ms | 100% |
| **NLI Verification (Airlock)** | **82ms** | **94.2% (Med-QA)** |
| Cryptographic Signing | 1ms | 100% |

---

## ⚠️ Known Limitations

- **NLI Thresholding**: The default 0.8 threshold may produce false negatives in highly creative writing tasks; it is tuned for *fact-based retrieval*.
- **Hardware Binding**: Keys are stored in the OS Keyring (Keychain/DPAPI). True hardware-anchored trust (TPM 2.0) is currently in development.
- **Context Window**: Verification latency scales linearly with the number of claims; massive responses (>2048 tokens) may see a lag.

---

## 🛡️ Security Model & Threat Considerations

- **Trust Assumptions**: We assume the host OS (Linux/Windows/macOS) is not compromised at the kernel level.
- **Out of Scope**: This stack does not protect against physical side-channel attacks on the CPU/RAM (yet).
- **Fail-Closed**: If the verification model fails to load or the signature chain is broken, the system **blocks** all output.

---

## 🗺️ Maturation Roadmap

- **Phase 1 (May 2026)**: Monorepo consolidation, Ed25519 forensics, NLI verification.
- **Phase 2 (Q3 2026)**: TPM 2.0 Hardware Binding, Secure Enclaves (Intel SGX).
- **Phase 3 (2027)**: Formal verification of the policy engine, Zero-Knowledge Proofs for compliance.

---

## 🤝 Contributing

We value "Brutal Feedback". Please report any architectural bypasses or cryptographic flaws in the Issues section.

---

## 📜 License
MIT
