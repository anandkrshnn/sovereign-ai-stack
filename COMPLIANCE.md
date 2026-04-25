# Compliance & Governance Mappings

This document outlines how the **Sovereign AI Stack** maps to major regulatory and auditing standards.

## 🏛️ Regulatory Mappings

| Standard | Requirement | Sovereign Stack Implementation |
| :--- | :--- | :--- |
| **HIPAA (Healthcare)** | §164.308(a)(1)(ii)(A) Risk Analysis | **local-rag** path isolation ensures PHI never enters multi-tenant pools. |
| **GDPR (Privacy)** | Article 32 (Security of Processing) | **local-bridge** ensures zero outbound data exfiltration by default. |
| **SOC 2 Type II** | CC6.1 Logical Access Security | **PolicyEngine** implements fail-closed ABAC at the retrieval gate. |
| **ISO 42001 (AI)** | Annex B (Data Governance) | **local-verify** provides objective, automated grounding scores for all outputs. |

## 🛡️ Sovereign Security Principles

### 1. Fail-Closed by Default
Any failure in the `PolicyEngine`, `SecretScanner`, or `AuditLogger` results in a total refusal of the AI response. We prefer silence over exposure.

### 2. Tamper-Evident Forensics
Audit trails use SHA-256 hash chaining. If any log entry is modified, the entire forensic chain Breaks, alerting auditors to tampering during the `local-agent` verification phase.

### 3. Local judge (The Verifier)
Hallucination is treated as a security risk. The **local-verify** component acts as a detached judge, scoring grounding and faithfulness. Answers below 0.85 are suppressed.

### 4. Data Residency
All data (Vector stores, SQLite, Logs) reside in user-controlled `/data/` directories. No telemetry or "home" calls are permitted.

---
*Last Verified: April 2026*
