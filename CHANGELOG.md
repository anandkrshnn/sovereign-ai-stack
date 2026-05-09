# Changelog

All notable changes to the Sovereign AI Stack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0a4] - 2026-05-09
### Added
- **Hardware-Anchored Merkle Checkpoints**: Integrated IETF RATS-compliant TPM quotes directly into forensic audit checkpoints, cryptographically binding Merkle Roots to PCR measurements.
- **Hardware Abstraction Layer (HAL)**: Refactored `hardware_trust` into a pluggable, multi-backend package supporting Linux TPM 2.0 (ESYS), Windows TPM (Structural), and High-Fidelity Software Simulation.
- **Fail-Closed Shutdown Integrity**: Implemented mandatory audit finalization on shutdown, ensuring the final Merkle state is hardware-attested before the system exits.
- **Unified Trust Factory**: Introduced `get_secure_anchor()` for automated, cross-platform hardware detection and graceful simulator fallback.

### Changed
- **Audit-to-Hardware Binding**: Updated `SovereignAuditLogger` to natively support `SecureAnchor` injection, ensuring non-repudiable forensic traces.
- **Interface Standardization**: Unified the `SecureAnchor` interface across all backends to resolve signature-related attribute errors.

## [0.1.0a3] - 2026-05-08
### Added
- **Remote Attestation Service**: Standalone FastAPI verifier for IETF RATS-aligned evidence validation.
- **Evidence Bundling**: Merkle Root binding to hardware quotes in `EvidenceBundle`.
- **Pydantic v2 Schemas**: Strict schema enforcement for `AttestationQuote` and `EvidenceBundle`.
- **RATS Alignment**: Formal separation of Attester (Node) and Verifier (Service) roles.

## [0.1.0a2] - 2026-05-08

### Added
- **Sovereign Airlock Middleware**: Formalized the verification gate as a pluggable `SovereignAirlock` interface, enabling multi-stage grounding and safety checks.
- **Verifiable Hardware Attestation**: Enhanced `hardware_trust.py` with `get_attestation_statement()`, allowing the audit chain to carry verifiable proof of hardware-bound trust.
- **Transparency Metadata**: Added `is_hardware_anchored` flags and attestation proofs to every audit record for full forensic transparency.
- **Reproducible Benchmark Harness**: Introduced `benchmark/harness.py` and a curated Med-QA adversarial dataset to empirically validate hallucination blocking rates.
- **Transparency Documentation**: Added "Transparency & Trust Boundaries" to README and reframed compliance docs as templates to clarify Research Preview status.

### Changed
- **Research Preview Alignment**: Downgraded "GA" branding to "Experimental Research Preview" across all package metadata and documentation.
- **Fail-Closed Verification**: Refactored the orchestrator to enforce a fail-closed verification posture via the new Airlock middleware.

## [0.1.0a1] - 2026-05-08

### Added
- **TPM P-256 Hardware Anchoring**: Integrated Windows TPM (via `ncrypt.dll`) for anchoring forensic audit chains to hardware root-of-trust.
- **Genesis Transition Protocol**: Implemented `GENESIS_TRANSITION` blocks to maintain forensic continuity across algorithm migrations (e.g., Ed25519 to P-256 Handover).
- **Adversarial Truncation Detection**: Added `SecurityHalt` triggers that detect and block attempts to truncate or manipulate historical audit records.
- **Unified Forensic Bridge**: Refactored the audit manager to support multi-version signature validation, bridging legacy hash chains with modern signed records.

### Fixed
- **Monorepo Dependency Gaps**: Resolved missing `tiktoken`, `duckdb`, and `opentelemetry` dependencies in the consolidated bridge orchestrator.
- **Hardware Lifecycle Cleanup**: Fixed TPM handle leaks and name errors in the `hardware_trust` module.

### Housekeeping
- Purged all compiled bytecode and binary SQLite artifacts from the repository history.
- Hardened `.gitignore` with strict environment and demonstration data patterns.

## [0.1.0-concept] - 2026-04-29

### Added
- **NLI Cross-Encoder Verification (Concept)**: Exploration of `DeBERTa-v3-base` for deterministic grounding.
- **Asymmetric Audit Signatures (Prototype)**: Initial implementation of Ed25519 for tamper-evident logs.
- **Local RAG Foundation**: Basic SQLite/LanceDB hybrid retrieval.
- **ABAC Policy Gateway**: Policy-first access control pattern.
