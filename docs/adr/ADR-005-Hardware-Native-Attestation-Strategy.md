# ADR-005: Hardware-Native Attestation Strategy

## Status
Accepted

## Implementation Note (2026-05-09)
The Pluggable HAL has been implemented in `sovereign_ai.common.hardware_trust`. For production stability, the Linux implementation uses high-level context management via `tpm2-pytss` for discovery and subprocess orchestration of `tpm2_quote` for robust evidence generation, bypassing memory handle constraints of pure ESAPI bindings.

### Verified Production Flow (2026-05-09)
The hardware attestation flow is now verified using an automated CI smoke test with `swtpm`. This test validates that `sovereign trust attest` produces cryptographically valid quotes bound to a challenge nonce, verifiable via `tpm2_checkquote`.

- **Handle Persistence**: AIK is persisted at `0x81000002`.
- **TCTI Interface**: Standardized on `swtpm` network sockets for containerized trust.
- **Verification**: Integrated `tpm2_checkquote` into the CI/CD pipeline.

## Context
The Sovereign AI Stack currently uses a high-fidelity software simulator (`MOCK_SIM`) for remote attestation. While this validates the IETF RATS protocol flow (ADR-004), it does not provide hardware-anchored trust. To reach production maturity, the stack must transition to native TPM 2.0 (Trusted Platform Module) quotes.

## Decision
We will implement a **Pluggable Hardware Abstraction Layer (HAL)** for attestation. This allows the stack to support multiple hardware backends (Linux TPM, Windows TPM, SGX) while maintaining a consistent interface for the audit and verifier layers.

### Key Architectural Components

1.  **Hardware Factory**: A centralized `get_secure_anchor()` function will detect the platform and available hardware, falling back to simulation if native hardware is missing.
2.  **Linux TPM (Priority 1)**: Initial native support will target Linux using the `python-tpm2-pytss` library (TSS2 stack).
3.  **Windows TPM (Priority 2)**: Structural support will be provided for Windows, with full integration planned for a later phase due to the complexity of Windows TPM services.
4.  **Graceful Degradation**: Production nodes will be configured to *require* hardware-native anchors, while development environments will default to simulators.

## Technical Requirements

### 1. The Quote Contract
The `SecureAnchor` must implement `generate_quote` which returns:
- **Signed PCR Values**: Measurements of the system state (e.g., PCR 0 for BIOS, PCR 11 for the Sovereign Application).
- **TPM-Signed Attestation Quote**: A binary blob (`TPM2B_ATTEST`) signed by an Attestation Identity Key (AIK).
- **AIK Public Certificate**: To allow the verifier to validate the signature.

### 2. Dependency Management
Native hardware support introduces complex system-level dependencies (e.g., `libtss2-esys`, `pkg-config`). These will be treated as **optional extras** in `pyproject.toml` to ensure the core stack remains lightweight and installable on all platforms.

```bash
pip install "sovereign-ai-stack[tpm2]"
```

## Consequences
- **Security**: Achieves hardware-anchored non-repudiation for audit logs.
- **Complexity**: Increases environment setup difficulty for native nodes.
- **Portability**: The factory pattern ensures the application logic remains platform-agnostic.
- **Testing**: Requires real TPM hardware (or an emulator like `swtpm`) for full CI/CD validation of native paths.
