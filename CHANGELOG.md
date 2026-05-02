# Changelog

All notable changes to the Sovereign AI Stack will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-04-29

### Added
- **NLI Cross-Encoder Verification**: Replaced generative LLM judges with `DeBERTa-v3-base` for deterministic, mathematically interpretable hallucination detection.
- **Ed25519 Asymmetric Audit Signatures**: Replaced basic SHA-256 hash chains with true cryptographic non-repudiation. Every event is signed with a private key stored in the OS keyring.
- **SHA-256 Linked Audit Chain**: Full tamper-evident forensic history.
- **Hybrid Retrieval**: Integrated BM25 lexical search with dense vector fusion.
- **ABAC Policy Enforcement**: Zero-trust role and classification-based access control before any retrieval.
- **Hardware-Backed Key Storage**: OS keyring integration (TPM/Keychain/DPAPI) for securing forensic signing keys.

### Performance
- **80ms Verification Latency**: 25x faster than previous Qwen generative judge (~2000ms).
- **92% Grounding Accuracy**: Benchmarked on healthcare and finance test sets.
- **100% Policy Enforcement**: Deterministic blocking of unauthorized intents or out-of-bounds queries.

### Security
- Ed25519 signatures ensure that audit logs cannot be spoofed or repudiated.
- OS-level credential management ensures signing keys are not exposed in plaintext `.env` files.
- Tamper-evident audit trail linking guarantees temporal integrity.
