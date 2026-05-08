# 🛡️ Sovereign AI Threat Model (v0.1.0a2)

This document identifies the security boundaries and adversarial risks of the Sovereign AI Stack, mapping them to the **STRIDE** methodology.

## 1. Trust Boundaries & Assumptions
- **TB1: Host OS Kernel**: We assume the underlying kernel (Windows/Linux/macOS) and its filesystem permissions are not compromised.
- **TB2: Secure Keyring**: We assume the OS-level secure storage (DPAPI/Keychain) provides isolation for the local `Master Key`.
- **TB3: Verification Model**: The NLI Cross-Encoder is treated as a "Semi-Trusted" component; we rely on its statistical performance, not formal proof.

## 2. STRIDE Risk Analysis

| Category | Risk Name | Description | Mitigation |
| :--- | :--- | :--- | :--- |
| **S**poofing | **Identity Forgery** | An attacker impersonates a valid Principal in the audit chain. | **TPM-Anchored Signing**: Ed25519 keys are bound to hardware (Windows) or software-simulated hardware. |
| **T**ampering | **Audit Truncation** | Deleting the last N records of the log to hide recent activity. | **Merkle Checkpoints**: Periodic Merkle roots are signed and hashed into the chain, preventing silent truncation. |
| **R**epudiation | **Forensic Denial** | A user claims they didn't run a prompt despite it being in the log. | **Hardware-Backed Timestamps**: Every log entry includes an immutable sequence and hash-chain link. |
| **I**nformation Disclosure | **Airlock Blindness** | LLM uses clever prompt injection to hide sensitive data in a "grounded-looking" answer. | **NLI Entailment + ABAC**: Policy engine filters retrieval *before* generation; Airlock verifies *after* generation. |
| **D**enial of Service | **Inference Overblocking** | The verifier blocks valid reasoning (The "Inference Gap"), rendering the AI useless. | **Roadmap: K-Gate**: Moving toward a knowledge-augmented ensemble to distinguish reasoning from hallucinations. |
| **E**levation of Privilege | **Policy Bypass** | Prompt injection bypasses the ABAC Policy Engine. | **Strict Schema Enforcement**: Input prompts are sanitized and passed through a constrained `Bridge` interface. |

## 3. High-Integrity Data Flow

1.  **Request**: User -> `Bridge` (Authenticated via Local Key).
2.  **Filter**: `PolicyEngine` (ABAC) filters RAG context based on Principal.
3.  **Generate**: LLM generates response using filtered context.
4.  **Airlock**: `SovereignEvaluator` calculates `grounding_score`.
5.  **Audit**: `SignedAuditChain` computes `curr_hash`, updates `Merkle Buffer`.
6.  **Checkpoint**: Every 10 events, a **Merkle Root** is signed and committed.

## 4. Specific Attack Surfaces

### AS1: The Verification Gate (Airlock)
- **Attack**: Adversarial prompt designed to trigger a "Neutral" NLI response while leaking info.
- **Surface**: The NLI model's latent space.
- **Maturity**: Low. Statistical validation is ongoing (see [Maturity Report](../benchmark/airlock_maturity.json)).

### AS2: Local Storage (Audit Logs)
- **Attack**: Modification of the `.audit` JSONL file.
- **Surface**: File system.
- **Maturity**: High. Merkle-linked hashing makes modifications computationally evident.

### AS3: Trusted Execution Fallback
- **Attack**: Forging a hardware attestation statement on a non-TPM system (macOS/Linux).
- **Surface**: The `hardware_trust.py` simulation layer.
- **Maturity**: Moderate. Clearly labeled as "Software Simulated" in logs to prevent false confidence.

---

## 5. Security Posture Roadmap
- [ ] **Phase 2**: Transition from Software Simulation to **Intel SGX Enclaves** for Mac/Linux.
- [ ] **Phase 2**: Formal verification of the `PolicyEngine` logic.
- [ ] **Phase 3**: Integration of **Zero-Knowledge Proofs** for cross-tenant audit verification.
