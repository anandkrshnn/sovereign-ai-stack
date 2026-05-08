# ADR 002: Asymmetric Forensic Audit Chain

## Status
Accepted (v0.1.0a2)

## Context
Standard application logs are vulnerable to retroactive tampering. If an attacker gains local access, they can delete or modify logs to hide unauthorized data extraction or policy violations.

## Decision
We implement a **Hash-Chained, Asymmetrically Signed Audit Trail** using Ed25519 or ECDSA P-256.

## Rationale
- **Non-Repudiation**: Asymmetric signatures ensure that only the holder of the private key (the system) could have generated the log.
- **Temporal Integrity**: Hash-chaining ensures that any deletion or insertion of a record breaks the sequential integrity of the chain.
- **Hardware Binding**: Asymmetric keys can be bound to a TPM or Secure Enclave, ensuring that the signing key never enters the main system memory.

## Consequences
- **Key Management**: Requires a robust lifecycle for provisioning and protecting signing keys.
- **Verification Overhead**: Every audit check requires public key validation, adding O(n) compute cost for full-chain verification.
- **Storage**: Audit records are larger due to the inclusion of signatures, public keys, and attestation proofs.
