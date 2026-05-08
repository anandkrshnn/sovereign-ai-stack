# Project Maturation Gates (v0.1.0a2)

This document defines the technical "Gates" required to transition the **Sovereign AI Stack** from Research Preview (Alpha) to Stable (v1.0.0).

## G1: Trust Anchoring (Hardware)
*   **Current State**: Software simulation on Mac/Linux; Native TPM 2.0 on Windows.
*   **Target**: Unified **IETF RATS** compliant Remote Attestation.
*   **Exit Criteria**: Successful `AIK` (Attestation Identity Key) quote verification on a remote challenger.

## G2: Forensic Integrity (Merkle Aggregation)
*   **Current State**: Merkle-linked blocks implemented in `audit.py`.
*   **Target**: Inclusion-proof verification in the UI.
*   **Exit Criteria**: Auditor can verify a specific `Request-ID` against a signed `Merkle Root` without access to the full log.

## G3: Verification Rigor (The Airlock)
*   **Current State**: 100% Recall on hallucinations, but 71.4% Precision due to the **"Inference Gap."**
*   **Hurdle: The Inference Gap**: The current NLI Cross-Encoder blocks valid logical inferences (e.g., medical BP ranges) because it lacks domain-specific knowledge.
*   **Maturation Target**: Implement a **Knowledge-Augmented Gate** (K-Gate).
    *   Inject ontologies (SNOMED-CT, Legal Codices) into the verification context.
    *   Use a Multi-Model Ensemble (Safety + Logic + Knowledge).
*   **Exit Criteria**: Achieve **>90% F1-Score** on the [Adversarial Dataset](../../tests/adversarial/adversarial_dataset.jsonl) while maintaining **100% Recall**.

## G4: Production Packaging
*   **Current State**: Script-based execution.
*   **Target**: Containerized "Sovereign Node."
*   **Exit Criteria**: Single `docker-compose up` launches a fully governed, verified, and audited stack.

---

### Phase Mapping
| Gate | Phase 1 (Current) | Phase 2 (Target) | Phase 3 (Future) |
| :--- | :--- | :--- | :--- |
| **G1** | Preview | Native RATS | Secure Enclaves |
| **G2** | Library | API Proofs | ZK-Proofs |
| **G3** | NLI Gate | **K-Gate (Ensemble)** | Formal Verification |
| **G4** | Local | Docker Node | Multi-Cloud Mesh |
