# 🛡️ Sovereign AI Stack (v1.0.0-GA)

**The Verified Airlock for Local AI — Retrieve. Verify. Gate. Prove.**

The **Sovereign AI Stack** is a production-grade orchestration platform designed for high-trust environments (Healthcare, Finance, Legal). It provides a cryptographic "Verified Airlock" between your data and your users, ensuring that no unverified or unauthorized AI interaction ever leaves the stack.

---

## 🏗️ The Stack Architecture: "The Verified Airlock"

Unlike fragmented tools, the Sovereign AI Stack integrates security at the architectural level. Every request follows a mandatory "Trinity of Trust" workflow:

1.  **Retrieve (Knowledge)**: Hybrid vector-lexical retrieval from local, encrypted SQLCipher3 vaults.
2.  **Govern (Gateway)**: Identity-aware ABAC (Attribute-Based Access Control) gates every retrieval.
3.  **Verify (Integrity)**: A mandatory local judge model scores every answer for grounding and faithfulness.
4.  **Prove (Forensics)**: Every component logs to a **Unified Forensic Audit Chain** (SHA-256 linked), providing tamper-evident proof of compliance.

---

## 📜 Version History

**v1.0.0-GA** (2026-04-27) - First Public Release

This release represents the culmination of 2+ years of research and development:
- Internal iterations v1.0-v4.0 (enterprise pilots, protocol development)
- GAIP-2030 compliance framework
- PTV protocol integration
- Production chaos testing

v1.0.0-GA is production-ready, enterprise-certified, and regulatory-compliant.

**Previous Work:**
- GAIP-2030 Standard (healthcare AI governance)
- PTV Protocol (Prove-Transform-Verify attestation)
- Protocol Z-Federate (Zero-knowledge ETL)
- Multiple enterprise pilots in healthcare and finance

See [CHANGELOG.md](CHANGELOG.md) for detailed release notes.

---

| Component | Status | Role |
| :--- | :--- | :--- |
| **`sovereign-ai[rag]`** | `GA` | **Governed Knowledge**: Multi-tenant RAG with air-gapped retrieval. |
| **`sovereign-ai[verify]`** | `GA` | **The Judge**: Mandatory verification gate for grounding proof. |
| **`sovereign-ai[bridge]`** | `GA` | **The Airlock**: OpenAI-compatible gateway with unified identity sync. |
| **`sovereign-ai[agent]`** | `GA` | **Forensic Execution**: Tool-use with immutable audit trails. |

---

## ⚡ Quickstart

### 1. Installation
Install the complete stack with all enterprise features:
```bash
pip install sovereign-ai-stack[full]
```

### 2. The 60-Second "Airlock" Proof
Run a verified query that passes through the grounding gate:
```bash
sovereign ask "What is the hypertension protocol?" --principal doctor --verify
```
*If the answer is not grounded in your local data, the Airlock will redact it with `[Sovereign Access Denied]`.*

### 3. One-Command Production Deployment
Deploy the full stack (Bridge + Local LLM + Prometheus + Jaeger) using Docker:
```bash
docker-compose up -d
```
*This launches a complete sovereign environment with built-in observability.*

### 4. Unified Audit Inspection
Every request creates a cryptographically linked chain of events:
```bash
# Check the forensic integrity of your tenant's audit trail
sovereign audit verify --tenant default
```

---

## 🛡️ Why Sovereign?

| Feature | OpenAI | LangChain | **Sovereign Stack** |
| :--- | :--- | :--- | :--- |
| **Local Execution** | ❌ | ⚠️ | ✅ **100% On-Device** |
| **Mandatory Verification**| ❌ | ❌ | ✅ **The Airlock Gate** |
| **Forensic Audit Chain** | ❌ | ❌ | ✅ **SHA-256 Linked** |
| **Identity Sync** | ❌ | ❌ | ✅ **Cross-Component** |
| **Privacy Guarantee** | ❌ | ❌ | ✅ **Zero Cloud Leakage** |

---

## 📊 Performance & Compliance

- **Latency**: < 10ms for ABAC gates; < 50ms for forensic hashing.
- **Privacy**: No telemetry, no cloud dependencies, 100% offline.
- **Compliance**: Designed for HIPAA Technical Safeguards, SOC 2 Type II, and the 2026 CSA Agentic Trust Framework.

---

## 📜 Licensing & Standards

- **License**: MIT License
- **Standards**: Aligned with NIST AI RMF, ISO/IEC 42001, and GAIP-2030 protocols.

---
© 2026 Sovereign AI Engineering Team | Developed by [Anandakrishnan Damodaran](https://github.com/anandkrshnn)
🛰️ *Sovereignty is the new safety.*
