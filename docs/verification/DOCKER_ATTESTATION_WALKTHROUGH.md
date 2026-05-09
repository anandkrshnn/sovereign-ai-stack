# DOCKER_ATTESTATION_WALKTHROUGH.md: Hardware-Native Validation (v0.1.0a2)

This document captures the exact CI assumptions and operational requirements for validating the Sovereign AI Stack's hardware-native attestation pipeline using a Docker-based TPM simulator.

## 1. CI Infrastructure Assumptions

The `Sovereign CI` workflow relies on the following infrastructure configuration:

- **Runner**: `ubuntu-latest` (GitHub-hosted runner).
- **Orchestration**: `docker compose` (V2 plugin).
- **Language Environment**: Python 3.10+ (via `actions/setup-python@v5`).
- **Dependencies**: The runner must have `docker` installed (standard on `ubuntu-latest`).

## 2. TPM Simulator Configuration (`swtpm`)

We use the `ghcr.io/stefanberger/swtpm:latest` image to provide a virtual TPM 2.0 interface. Key operational parameters include:

- **Interface**: Network Socket (TCP).
- **Ports**: 2321 (Command), 2322 (Control).
- **State**: Ephemeral (reset per job run).
- **TCTI Path**: `swtpm:host=tpm-simulator,port=2321`.

## 3. Mandatory Initialization Sequence

TPM simulators require a specific startup sequence to avoid memory exhaustion and state errors:

1.  **`tpm2_startup -c`**: Mandatory. Initializes the TPM state after the container starts.
2.  **`tpm2_clear -c o`**: Clears the Owner hierarchy to ensure a clean slate for provisioning.
3.  **Aggressive Flushing**: Before and after sensitive operations (like `tpm2_load`), we run `tpm2_flushcontext [-t|-l|-s]` to free up transient object slots. This prevents `0x902` (Out of Memory) errors.

## 4. Attestation Smoke Test Logic

The `scripts/verify_attestation.py` script performs the following steps to verify cryptographic integrity:

### A. Provisioning
- Creates an Endorsement Primary Key (`tpm2_createprimary`).
- Generates a restricted RSA-2048 signing key (Attestation Identity Key - AIK).
- Persists the AIK to a fixed handle (`0x81000002`).

### B. Execution
- Triggers `sovereign trust attest --nonce <nonce>` inside the container.
- The stack detects the `TPM2LinuxAnchor` and requests a hardware quote from the simulator.
- The simulator signs the Merkle Root of the current audit state using the AIK.

### C. Cryptographic Verification
- The script extracts the `quote_data` and `signature` from the stack's JSON output.
- It extracts the AIK public key from the TPM in PEM format.
- It runs `tpm2_checkquote` to cryptographically verify that the signature is valid, matches the AIK public key, and is bound to the original nonce.

## 5. Troubleshooting (Error Reference)

| Error Code | Meaning | Fix |
|---|---|---|
| `0x100` | TPM Not Started | Ensure `tpm2_startup -c` was called. |
| `0x902` | Out of Memory | Flush transient objects via `tpm2_flushcontext -t`. |
| `127` | Command Not Found | Verify `docker compose` (V2) or `python` paths. |
| `0x143` | Handle Not Found | AIK at `0x81000002` was not provisioned or was evicted. |

---
*Verified Milestone: v0.1.0a2-docker-attestation*
