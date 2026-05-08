# Known Architectural Gaps (v0.1.0a2)

This document honestly tracks the discrepancies between the **Sovereign AI Stack** target architecture and its current implementation.

### 1. Orchestration Bottleneck
- **Status**: The `pipeline.py` file acts as a monolithic orchestrator. 
- **Gap**: The C4 diagram implies decoupled containers, but execution is currently synchronous and tightly coupled within the package root.
- **Remediation**: Planned refactor to `ForensicMiddleware` in Phase 6.

### 2. Hardware Root-of-Trust Fallback
- **Status**: macOS and Linux currently use a software-based `SoftwareSimulatorAnchor`.
- **Gap**: The "Hardware-Anchored" claim is only natively true for Windows TPM 2.0 at this time.
- **Remediation**: Implementing native `CryptoKit` (macOS) and `tpm2-tools` (Linux) integrations.

### 3. Remote Attestation (RATS)
- **Status**: The stack uses local signing.
- **Gap**: There is no external challenger/verifier for the hardware identity.
- **Remediation**: Implementing the [rats.py](../../sovereign_ai/common/rats.py) protocol drafted in Phase 6.

### 4. Zero-Stars / External Validation
- **Status**: The project is a new Research Preview with 0 external audits.
- **Gap**: Architectural claims have not yet been peer-reviewed or field-tested.
- **Remediation**: Seeking independent security audits and community red-teaming in Q3 2026.
