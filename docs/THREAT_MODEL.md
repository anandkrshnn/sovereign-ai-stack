# Sovereign AI Stack - Threat Model & STRIDE Analysis

## Architecture Overview
The Sovereign AI Stack is designed under a **Verify-First + Brutal Minimalism** philosophy. It guarantees cryptographic non-repudiation, entailment verification, and secure hardware bindings.

## STRIDE Analysis (v2.2 Hardened)

| Threat Category | Component | Attack Vector | Mitigation in v2.2 |
| :--- | :--- | :--- | :--- |
| **Spoofing** | TPM / Mock Sim | Forging mock attestation quotes using predictable symmetric hashes (`sim_pcr_N`). | **MITIGATED:** Strict `SOVEREIGN_ENV=production` guard halts execution if hardware simulation is detected in production. |
| **Tampering** | Audit Chain | Truncating the `_get_last_record_fast` backward-seek reader mid-JSON to rewind the Merkle chain. | **MITIGATED:** Append-only with `os.fsync` for durability. Cryptographic hashes tie sequential events. |
| **Repudiation** | Hardware Trust | Exhausting TPM transient objects to force fallback to simulation. | **MITIGATED:** Ed25519 signatures generated within hardware. Fallbacks strictly forbidden in production context. |
| **Information Disclosure** | Memory / Keys | `seal_key` and `unseal_key` leaving plaintext key bytes in Python memory, vulnerable to core dumps. | **MITIGATED:** Implemented `secure_zero` utilizing `ctypes` to wipe `plaintext_key` buffers immediately after use. |
| **Denial of Service** | NLI Gate | PyTorch NLI models running synchronously and blocking the `asyncio` event loop. | **MITIGATED:** Wrapped `get_probabilities` inference in `asyncio.to_thread` to release the GIL and allow async throughput. |
| **Elevation of Priv.** | LangChainGuard | Prompt injections tricking the LLM to trigger a malicious tool call that mathematically entails the context. | **ACCEPTED RISK:** Addressed partially via LangChain guardrails. Strict tool-use sandboxing required at the OS level. |

## Assumptions
- The physical host TPM 2.0 is not physically compromised.
- The base OS has secure boot enabled.
- Tenant IDs are managed by a secure identity provider.
