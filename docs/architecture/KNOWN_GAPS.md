# Known Architectural Gaps & Disclosures (v0.1.0a5)

This document honestly tracks the discrepancies between the **Sovereign AI Stack** target architecture and its current implementation state.

### 1. Hardware Root-of-Trust (Simulator Dependency)
- **Status**: Native TPM 2.0 (ESYS) support is live for Linux, but primarily tested using the `swtpm` simulator in CI.
- **Gap**: While the code uses the same ESAPI calls as physical hardware, performance and state-leakage characteristics of real physical TPMs (especially regarding transient object slots) may differ.
- **Remediation**: Validating on physical Intel/AMD TPMs and implementing proper `NCrypt` support for Windows (currently using a functional mock).

### 2. Remote Verifier Maturity
- **Status**: The [AttestationVerifier](../../sovereign_ai/common/rats.py) now performs real RSA-PSS signature verification.
- **Gap**: The "Reference Values" (Reference Integrity Manifests) are currently hardcoded or passed manually. There is no automated platform measurement service (like a centralized Attestation Authority).
- **Remediation**: Phase 4 will introduce an automated RIM discovery protocol.

### 3. Adversarial Depth
- **Status**: A "Red Team" test suite exists to check for quote replay and PCR modification attempts.
- **Gap**: The testing is not yet comprehensive enough to cover side-channel attacks, supply-chain poisoning of the `tpm2-pytss` library, or sophisticated "Confused Deputy" attacks on the NLI judge.
- **Remediation**: Ongoing adversarial analysis and expansion of the `tests/red_team` suite.

### 4. Claims vs. Maturity Alignment
- **Status**: The README promotes "Verified Airlocks" and "Forensic Audit Chains".
- **Gap**: These are alpha-stage protocols. The "Verified Airlock" relies on a local NLI model which has its own false-positive/negative rates.
- **Remediation**: Updated documentation to strictly use "Alpha" and "Research Prototype" labels throughout.

### 5. Deployment coupling
- **Status**: The `pipeline.py` is still the primary orchestrator.
- **Gap**: In a production "Sovereign" environment, the verifier and the executor should be on physically or logically isolated systems. Currently, they often run in the same container environment.

---
*Last Audit: May 2026*
