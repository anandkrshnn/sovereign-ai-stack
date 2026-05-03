# 🛡️ Sovereign AI Threat Model

**Version**: 0.1.0-alpha  
**Scope**: Local-First RAG Stack

## 1. Trust Assumptions
- **Host Integrity**: We assume the underlying Operating System and Hardware are not compromised.
- **Local Isolation**: We assume the local file system provides basic read/write protection between user accounts.
- **Key Storage**: We trust the OS-level secure storage (Apple Keychain, Windows DPAPI, Linux Secret Service) to protect private Ed25519 keys.

## 2. Adversarial Personas
| Persona | Goal | Capability |
|---|---|---|
| **Malicious User** | Extract unauthorized data | Prompt injection, credential stuffing. |
| **Tampering Actor** | Modify audit logs to hide actions | Local file system access. |
| **Model Poisoner** | Bias the NLI verifier | Providing malicious training data (Out of scope). |

## 3. High-Level Data Flow
1. **Input**: User prompt enters the `Bridge`.
2. **Retrieve**: Context pulled from `SQLite/LanceDB`.
3. **Govern**: `PolicyEngine` applies ABAC rules.
4. **Verify**: `SovereignEvaluator` (NLI) checks grounding.
5. **Output**: Verified answer returned with signed `AuditRecord`.

## 4. Key Risks & Mitigations

### R1: Hallucination Bypass
- **Risk**: The LLM generates a convincing but false answer that confuses the NLI verifier.
- **Mitigation**: Fail-closed logic on low NLI scores (<0.8) and mandatory citation of source chunks.

### R2: Audit Log Tampering
- **Risk**: An attacker deletes or modifies the forensic log to hide data extraction.
- **Mitigation**: **Ed25519 Signatures** and Hash-Chaining. Any modification breaks the chain and fails the `verify_integrity()` check.

### R3: Key Extraction
- **Risk**: A local attacker extracts the Ed25519 private key to forge audit logs.
- **Mitigation**: Keys are stored in the OS secure keyring, not as plaintext files. Future work: TPM 2.0 binding.

---

## 5. Out of Scope
- Protection against physical RAM dumping or Cold Boot attacks.
- Network-level protection (Bridge is assumed to run on `localhost` or via encrypted VPN).
- LLM weights protection (weights are assumed public or locally controlled).
