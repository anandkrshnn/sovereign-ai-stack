# Linux Field Test Plan: Native TPM 2.0 Attestation

This document outlines the procedure for validating the **Hardware-Native Attestation** layer of the Sovereign AI Stack on physical Linux hardware or specialized TEE environments (e.g., Azure CVM, AWS Nitro).

## 1. Prerequisites

### 1.1 System Libraries
The native bridge requires the Trusted Computing Group (TCG) TSS2 stack.
```bash
sudo apt update
sudo apt install libtss2-esys0 libtss2-tctildr0 libtss2-rc0
```

### 1.2 Python Dependencies
Ensure the `tpm2` extra is installed.
```bash
pip install sovereign-ai-stack[tpm2]
```

### 1.3 Device Access
The user must have read/write access to the TPM Resource Manager (`/dev/tpmrm0`).
```bash
# Check access
ls -l /dev/tpmrm*

# If necessary, add current user to 'tss' group or adjust udev rules
sudo usermod -aG tss $USER
# (Requires logout/login)
```

---

## 2. Environment Verification

Run the following command to verify that the TSS2 stack can see your hardware:
```bash
tpm2_pcrread sha256:0,11
```
If this fails, the Python implementation will fallback to **Simulation Mode**.

---

## 3. Test Procedures

### Test 1: Identity & Public Key Retrieval
**Objective**: Verify that the AIK can be retrieved from a persistent handle.
1. Run the sovereign CLI:
   ```bash
   sovereign trust status
   ```
2. **Success Criteria**: 
   - `Anchor Type`: `TPM2LinuxAnchor`
   - `Hardware`: `True`
   - `Algorithm`: `RSA2048`
   - `Public Key`: Should display a valid PEM block or hash.

### Test 2: Hardware-Native Signing
**Objective**: Ensure the TPM can sign arbitrary audit payloads.
1. Generate a test signature:
   ```bash
   echo "forensic-integrity-test" > test.txt
   sovereign trust attest --nonce $(sha256sum test.txt | awk '{print $1}')
   ```
2. **Success Criteria**: 
   - No `Warning: AIK Handle not found` in logs.
   - Output contains a `signature` field starting with a base64-encoded binary blob (not a `TPM_SIM_` string).

### Test 3: IETF RATS Quote Generation
**Objective**: Generate a fresh attestation quote bound to a nonce.
1. Run a full attestation:
   ```bash
   sovereign trust attest --nonce "field-test-nonce-001" --pcr 0,11
   ```
2. **Success Criteria**:
   - `Evidence Type`: `tpm2_quote`
   - `PCR Values`: Should contain hexadecimal measurements of your actual system firmware (PCR 0) and application state (PCR 11).
   - `Quote Data`: A long base64 string (TPMS_ATTEST structure).

### Test 4: Pipeline Enforcement (Fail-Closed)
**Objective**: Verify that the pipeline blocks operation if trust is compromised.
1. Set an invalid verifier URL:
   ```bash
   export SOVEREIGN_REQUIRE_REMOTE_ATTESTATION=true
   export SOVEREIGN_REMOTE_VERIFIER_URL="http://invalid-verifier.local"
   ```
2. Attempt to start a RAG session:
   ```bash
   sovereign chat
   ```
3. **Success Criteria**:
   - Application must terminate with `sovereign_ai.common.schemas.SecurityHalt`.
   - Error message: `Verifier Unreachable`.

---

## 4. Troubleshooting

| Error Code | Potential Cause | Solution |
| :--- | :--- | :--- |
| `0x00000081` | Handle Not Found | AIK has not been provisioned at `0x81010001`. Use `tpm2_createprimary` + `tpm2_create` + `tpm2_evictcontrol`. |
| `Permission Denied` | `/dev/tpmrm0` lock | Ensure no other process (like `fwupd`) has an exclusive lock, or check group permissions. |
| `ImportError` | Missing `tpm2-pytss` | Run `pip install tpm2-pytss`. Note: requires `gcc` and `python3-dev` to compile. |

---

## 5. Reporting
Please document the output of `sovereign trust status` and any ESYS error codes encountered during the field test for the v0.1.0a5 validation report.
