# Sovereign AI Attestation Verifier

The Attestation Verifier is a standalone service implementing the **IETF RATS (Remote ATtestation ProcedureS)** framework. It acts as a trusted third party that validates cryptographic evidence produced by Sovereign Nodes.

## Overview

In the Sovereign AI Stack, trust is not assumed—it is verified. Every **Merkle Checkpoint** produced by a node is bundled with hardware-attested evidence (a "Quote") and sent to this verifier.

### Key Features
- **RATS Alignment**: Separates Attester (Node) from Verifier (Service).
- **Hardware Binding**: Validates that audit logs were produced by a measured, unmodified TPM-backed runtime.
- **Anti-Replay**: Enforces nonce-bound challenges to prevent replay attacks.
- **Pydantic v2 Enforcement**: Strict schema validation for all attestation evidence.

## API Specification

### 1. Health Check
`GET /health`
- **Purpose**: Verify service availability.
- **Response**: `{"status": "operational", "timestamp": "..."}`

### 2. Verify Evidence
`POST /verify`
- **Purpose**: Validate an `EvidenceBundle` against a known "Golden" reference hash.
- **Request Body**:
```json
{
  "bundle": {
    "version": "1.0",
    "nonce": "32-character-challenge-nonce",
    "merkle_root": "0x...",
    "quote": {
      "type": "TPM2_QUOTE",
      "quote_data": "base64_data",
      "pcr_values": {"0": "bios_hash", "11": "app_hash"},
      "runtime_measurement": "golden_binary_hash",
      "signature": "aik_signature"
    },
    "bundle_signature": "attester_signature"
  },
  "expected_nonce": "32-character-challenge-nonce",
  "reference_version": "v0.1.0a2"
}
```
- **Response**:
```json
{
  "is_valid": true,
  "verified_at": "...",
  "checks": {
    "nonce_fresh": true,
    "measurements_valid": true,
    "signature_valid": true
  },
  "errors": [],
  "evidence_type": "TPM2_QUOTE"
}
```

## Running the Service

The verifier is a FastAPI application.

```bash
# From the project root
python sovereign_ai/services/verifier.py
```

## Security Model
The verifier relies on **Reference Values** (Golden Hashes) to detect tampering. If the `runtime_measurement` in a quote does not match the known hash for that version, verification will fail.
