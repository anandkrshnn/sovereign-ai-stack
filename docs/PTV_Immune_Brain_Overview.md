# Sovereign AI Stack: Prove-Transform-Verify (PTV) and Immune System Brain

## Executive Summary for IMDA Singapore
This document outlines the architecture and enforcement mechanisms of the **Immune System Brain**, a core component of the Sovereign AI Stack, designed to align with Singapore's AI Governance Framework and AI Verify guidelines. 

The Immune System Brain enforces a **Verify-First, Fail-Closed, Fully Sovereign** architecture. By anchoring cryptographic identity to hardware (TPM 2.0) and utilizing Zero-Knowledge Proofs (Groth16), the system ensures that only mathematically proven, policy-compliant knowledge can enter the AI's core memory.

## Architecture

The Immune System Brain operates through a strict, multi-layered defense mechanism:

1. **PTV Bridge (Airlock)**
   - Before any knowledge event (Antigen) is considered, it must pass through the PTV Bridge.
   - Requires a valid Groth16 Zero-Knowledge proof and TPM 2.0 PCR attestation.
   - Binds the event cryptographically using Ed25519 signatures.
   - Ensures mathematical certainty of the agent's identity and operational state without exposing sensitive keys.

2. **NLI Adaptive Gate (Innate Immunity)**
   - Once cryptographically verified, the event payload is evaluated by a local DeBERTa-v3 cross-encoder.
   - The gate checks for logical consistency, entailment, or contradiction against the existing verified knowledge base (Layer 1).
   - If a direct contradiction is detected, the event is rejected (Fail-Closed).
   - Ambiguous inputs are sent to a Quarantine Zone for manual or algorithmic resolution.

3. **Cryptographic Merkle Chain (Layer 0 Vault)**
   - All events, regardless of acceptance or rejection, are hashed and appended to a cryptographic Merkle tree.
   - This provides an immutable, forensic audit trail of all attempted knowledge modifications, essential for regulatory compliance and incident response.

4. **Autoimmune Safeguard**
   - The system monitors rejection rates over a sliding window.
   - If the rejection rate spikes (e.g., indicating a coordinated knowledge poisoning attack), the system dynamically increases its strictness thresholds, restricting what can be added to the verified memory until the threat subsides.

## Alignment with AI Verify
- **Transparency & Explainability**: Every knowledge update is logged with a cryptographic hash, allowing full traceability of *who* proposed *what* and *why* it was accepted or rejected.
- **Security & Resilience**: The integration of TPM 2.0, Groth16 proofs, and the Autoimmune Safeguard provides robust defense against knowledge poisoning and unauthorized access.
- **Accountability**: The mandatory Ed25519 signatures ensure non-repudiation for all agent actions.
