# Hardware Trust Abstraction Layer (HAL)

This package provides a pluggable interface for hardware-anchored trust in the Sovereign AI Stack. It implements the **IETF RATS** (Remote ATtestation ProcedureS) evidence generation roles.

## Architecture

The HAL uses a **Factory Pattern** to detect and initialize the best available security anchor for the current host platform.

### Supported Anchors
1.  **Software Simulator (`MOCK_SIM`)**: Default for development and CI. Uses local Ed25519 keys to simulate hardware signatures.
2.  **Linux TPM 2.0 (`TPM2_QUOTE`)**: Native hardware attestation using the TSS2 stack (`python-tpm2-pytss`). Requires `/dev/tpmrm0` access.
3.  **Windows TPM 2.0**: Structural placeholder for Windows TPM Services integration.
4.  **Legacy Anchor**: Backward compatibility for non-attested audit signing.

## Usage

### 1. Programmatic Access
```python
from sovereign_ai.common.hardware_trust import get_secure_anchor

# Auto-detect best backend (TPM2 on Linux, Simulator on Windows/macOS)
anchor = get_secure_anchor(tenant_id="tenant_a")

# Generate an attestation quote
quote = anchor.generate_quote(nonce="32_byte_random_challenge", pcrs=[0, 11])
```

### 2. CLI Access
```bash
# Generate a simulated quote
sovereign-ai trust attest --backend mock

# Force native Linux TPM (fails if no TPM present)
sovereign-ai trust attest --backend tpm2_linux
```

## Platform Support
- **Linux**: Full native support (Priority 1) via TSS2.
- **Windows**: High-fidelity simulation + structural TPM placeholder.
- **CI/CD**: Always defaults to `mock` simulation for deterministic pipeline runs.

## Dependencies
Native hardware support is optional. Install with:
```bash
pip install "sovereign-ai-stack[tpm2]"
```
