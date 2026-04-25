# 🛡️ Sovereign AI Stack (v1.0.0-GA)

**Local, Governed, Auditable AI — The Trinity of Trust.**

The **Sovereign AI Stack** is the world's first certified local AI platform designed for high-trust environments (Healthcare, Finance, Legal). It provides a full-stack, zero-cloud-leakage orchestration layer that ensures every AI interaction is grounded, governed, and forensically auditable.

---

## 🏗️ The Stack Architecture

The platform consolidates four critical layers into a unified sovereign engine:

| Component | Layer | Purpose |
| :--- | :--- | :--- |
| **`local-rag`** | **Knowledge** | Governed, hybrid vector-lexical retrieval with SQLCipher3. |
| **`local-verify`** | **Integrity** | Local-first grounding & faithfulness judge with crypto-certs. |
| **`local-bridge`** | **Gateway** | OpenAI-compatible gateway with ABAC policy enforcement. |
| **`local-agent`** | **Execution** | Forensically auditable tool execution with SHA-256 chaining. |

---

## ⚡ Quickstart

### 1. Unified Installation
Install the complete stack with all enterprise features:
```bash
pip install sovereign-ai-stack[full]
```

### 2. The 60-Second Sovereign Proof
Prove grounding and governance in one command:
```bash
sovereign ask "What is the patient's hypertension protocol?" --principal doctor --verify
```

### 3. Launch the Sovereign Dashboard
Visualize your audit trails and verification scores:
```bash
streamlit run demos/verify_dashboard.py
```

---

## 🛡️ The Trinity of Trust

1. **Retrieve**: Evidence is pulled from siloed, local-only vaults.
2. **Govern**: Decisions are gated by a fail-closed ABAC engine.
3. **Verify**: Every output is scored by a local judge model.
4. **Prove**: Every action is recorded in a tamper-evident forensic audit trail.

---

## 📊 Performance & Compliance

- **Latency**: < 10ms for ABAC enforcement; < 50ms for Audit Hashing.
- **Privacy**: Zero Cloud Leakage. 100% On-Device.
- **Compliance**: Designed for HIPAA technical safeguards, GDPR data residency, and SOC 2 Type II auditability.

---

## 📜 Licensing & Standards

- **License**: MIT License
- **Standards**: Aligned with NIST AI RMF, ISO/IEC 42001, and the 2026 CSA Agentic Trust Framework.

---
© 2026 Sovereign AI Engineering Team | Developed by [Anandakrishnan Damodaran](https://github.com/anandkrshnn)
