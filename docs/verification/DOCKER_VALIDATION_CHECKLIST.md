# Docker Validation Checklist: Hardware-Native Path (v0.1.0a5)

Follow this checklist after running `docker-compose up --build` to confirm the Sovereign AI Stack is correctly utilizing the Linux ESYS path.

## 1. Environment Health
- [x] **swtpm Startup**: Verified via `docker-compose up`.
- [x] **TCTI Connectivity**: Verified via `TPM2TOOLS_TCTI` environment propagation.

## 2. Hardware Trust Detection
Run `docker exec sovereign-app sovereign trust status`.
- [x] **Anchor Type**: `TPM2LinuxAnchor` (Verified via `sovereign trust attest --backend tpm2_linux`).
- [x] **Hardware Status**: `True`.
- [x] **Algorithm**: `RSA2048`.

## 3. Cryptographic Handshake
Run `docker exec sovereign-app sovereign trust attest --nonce docker-test-123`.
- [x] **Signature Presence**: Verified in JSON output.
- [x] **Quote Validity**: Verified via `tpm2_checkquote` in CI.
- [x] **PCR Visibility**: PCRs 0 and 11 correctly measured and reported.

## 4. Pipeline Guardrails
Attempt to start a chat with remote attestation forced:
`docker exec -e SOVEREIGN_REQUIRE_REMOTE_ATTESTATION=true sovereign-app sovereign chat`.
- [ ] **Security Halt**: Since no verifier service is running at `localhost:8000` (default), the pipeline should exit with a `SecurityHalt` error.
  - Expected log: `CRITICAL: SECURITY_HALT - Verifier Service Unreachable`.

---

## What "Failure" Looks Like
If you see any of the following, the validation has **FAILED**:
1. `Anchor Type: SoftwareSimulatorAnchor` inside the Linux container.
2. `ImportError: cannot import name 'ESYS_CONTEXT' from 'tpm2_pytss'`.
3. `TSS2_RC_TCTI_IO_ERROR` (indicates the app can't reach the `swtpm` container).
