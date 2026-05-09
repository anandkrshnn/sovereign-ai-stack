# ADR-004: Remote Attestation Protocol (IETF RATS Alignment)

## Status
Proposed (v0.1.0a2)

## Context
The Sovereign AI Stack currently uses local TPM 2.0 (Windows) or software simulation (macOS/Linux) to sign audit logs. While this provides local tamper-evidence, it does not allow a remote third party (an "Auditor" or "Relying Party") to cryptographically verify that the logs were produced by a specific, unmodified version of the Sovereign AI software running in a trusted environment.

## Decision
We will implement a **Remote Attestation Protocol** based on the **IETF RATS (Remote ATtestation ProcedureS)** framework. This will transition the stack from "Local Trust" to "Verifiable Remote Trust."

### 1. Architectural Roles (RATS Mapping)
- **Attester**: The Sovereign AI Stack instance generating evidence (Quote + Measurements).
- **Verifier**: A standalone service (or logic block) that validates the Evidence against "Endorsements" and "Reference Values."
- **Relying Party**: The Auditor or UI that consumes the "Attestation Result" to trust the Audit Log.

### 2. Evidence Schema (The "Attestation Bundle")
The Attester will produce a signed bundle for every **Merkle Checkpoint**. We will use **Pydantic v2** for schema enforcement.

#### Evidence Types:
- `TPM2_QUOTE`: Standard hardware quote using PCRs.
- `SGX_REPORT`: Confidential computing report.
- `MOCK_SIM`: Software-simulated attestation for non-TPM environments.

#### Primary Measurements:
- **PCR 0**: BIOS/Firmware measurements (Hardware Trust).
- **PCR 11**: Application-level state (Sovereign Binary + Policy Engine Hash).

### 3. Verification Sequence
```mermaid
sequence_diagram
    participant RP as Relying Party (Auditor)
    participant V as Verifier Service
    participant A as Attester (Sovereign AI)

    RP->>A: Challenge(Nonce)
    A->>A: Gather Measurements(PCR 0, PCR 11, Merkle Root)
    A->>A: Generate TPM2_Quote(Nonce, PCRs)
    A->>A: Sign EvidenceBundle(AIK)
    A->>RP: Attestation Bundle
    RP->>V: Validate(Bundle, Nonce, Reference Values)
    V->>V: Check Signature(AIK Cert)
    V->>V: Check Measurements(Golden Hashes)
    V-->>RP: Attestation Result (Pass/Fail)
```

## Consequences
- **Positive**: Enables "Zero-Trust" auditing where the Auditor doesn't have to trust the host OS.
- **Negative**: Requires maintaining a registry of "Golden Hashes" for every binary release.
- **Dependency**: Integration with `python-tpm2-pytss` or `tss2` libraries.

## References
- [IETF RATS Architecture (RFC 9334)](https://datatracker.ietf.org/doc/rfc9334/)
- [TPM 2.0 Library Specification](https://trustedcomputinggroup.org/resource/tpm-library-specification/)
