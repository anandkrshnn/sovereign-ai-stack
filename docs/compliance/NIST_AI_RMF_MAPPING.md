# NIST AI Risk Management Framework (RMF 1.0) Mapping

> [!IMPORTANT]
> **Regulatory Disclaimer**: This mapping is intended for **informational and architectural guidance** only. It supports organizational risk and governance documentation but does **not** constitute a formal audit or proof of production compliance. This is a technical reference for an Alpha Research Preview.

This document identifies how the **Sovereign AI Stack** technical features align with the NIST AI RMF functions to support organizational governance.

| Function | Category | Sovereign AI Stack Implementation | Status |
| :--- | :--- | :--- | :--- |
| **GOVERN** | GOVERN 1.2 | `PolicyEngine` (ABAC) enforces organizational rules before model interaction. | Stable |
| **GOVERN** | GOVERN 2.1 | `SignedAuditChain` provides an immutable record of all AI system inputs/outputs for external oversight. | Alpha |
| **MAP** | MAP 1.1 | [THREAT_MODEL.md](../THREAT_MODEL.md) documents identified risks and trust boundaries. | Active |
| **MEASURE** | MEASURE 1.1 | `benchmark/harness.py` provides reproducible metrics for hallucination rates (NLI scores). | Active |
| **MEASURE** | MEASURE 2.1 | `calibration.py` empirically determines optimal verification thresholds to balance false negatives/positives. | Active |
| **MANAGE** | MANAGE 1.1 | `SovereignAirlock` (Ensemble) acts as a fail-closed gate to block ungrounded or out-of-policy claims. | Experimental |
| **MANAGE** | MANAGE 1.2 | `SecureAnchor` (TPM 2.0) ensures cryptographic integrity of audit logs, preventing management override of forensic evidence. | Alpha |

## Technical Evidence for Auditors
1. **Verifiable Grounding**: See `sovereign_ai/verify/ensemble.py` for multi-stage validation logic.
2. **Forensic Traceability**: See `sovereign_ai/common/audit.py` for Ed25519 signature implementation.
3. **Hardware Integrity**: See `sovereign_ai/common/hardware_trust.py` for Windows TPM 2.0 integration.
