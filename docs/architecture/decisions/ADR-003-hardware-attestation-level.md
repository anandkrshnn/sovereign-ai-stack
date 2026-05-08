# ADR 003: Hardware Attestation Level

## Status
Accepted (v0.1.0a2)

## Context
The stack claims "Hardware-Anchored" forensics. Current implementation includes native Windows TPM 2.0 signing and a software fallback for other platforms.

## Decision
We define the current state as a **Hardware-Targeted Preview**, not a full **Remote Attestation (RATS)** system.

## Rationale
- **Development Maturity**: A full implementation of Attestation Identity Keys (AIK) and Quote verification requires significant infrastructure that is out of scope for the v0.1.0 Alpha.
- **Path to Integrity**: By establishing the `SecureAnchor` interface now, we ensure that the "Basic" software signing can be swapped for "Proper" TPM-bound RATS without refactoring the entire audit layer.

## Future Goal
Full implementation of IETF RATS-compliant Attestation Statements using native TPM/HSM keys that are non-exportable and verified via an external challenger.
