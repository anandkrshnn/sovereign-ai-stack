# Sovereign AI Stack: Technical Architecture

The Sovereign AI Stack is a Layer 3 orchestration platform designed to provide a "Verified Airlock" for local AI agents. This document details the cryptographic and structural principles that enable "Proven Sovereignty."

## 1. The Trinity of Trust (Pipeline)

The stack operates as a linear, fail-closed pipeline:

1. **RETRIVE (Local RAG)**: 
   - Uses a Hybrid Search architecture: **FTS5 (BM25)** for keyword matching + **LanceDB (Vector)** for semantic similarity.
   - **BGE-Reranker** cross-encoders refine the top-K results for maximum precision.

2. **GOVERN (ABAC Engine)**:
   - Every request is intercepted by an Attribute-Based Access Control (ABAC) engine.
   - Matches Principal attributes (Role, Classification) against Resource attributes (Tenant, Security Level).
   - Fail-Closed: If no policy explicitly allows the interaction, it is denied by default.

3. **VERIFY (Local Judge)**:
   - A dedicated local judge model (Sentence-Similarity or SLM) evaluates the LLM's response against the retrieved evidence.
   - **Grounding Score**: Uses a threshold (default 0.85) to ensure the answer is grounded in the provided context.
   - Responses below the threshold are redacted or blocked.

4. **PROVE (Forensic Audit)**:
   - Every event (Request, Retrieval, Decision, Response) is hashed via SHA-256 with canonical JSON serialization.
   - **Chaining**: Each record contains the `prev_hash`, creating a cryptographically linked history.
   - **Asymmetric Anchoring**: The final state hash is signed using an **Ed25519 digital signature**, enabling public verifiability.
   - **Secure Key Storage**: The Ed25519 private key is provisioned and stored using **OS-backed secure storage** (Windows Credential Manager or macOS Keychain), protecting the forensic identity from simple filesystem access.

## 2. Component Layout

- **`SovereignPipeline`**: The primary facade for developer integration.
- **`SovereignBridge`**: OpenAI-compatible API gateway.
- **`LocalRAG`**: High-performance retrieval engine.
- **`AuditChainManager`**: The cryptographic backend for forensic logging.

## 3. Compliance Framework

The architecture is designed to map directly to:
- **HIPAA Technical Safeguards**: Audit controls (§164.312(b)) and Integrity (§164.312(c)(1)).
- **SOC2 Type II**: Trust Services Criteria (Security, Confidentiality).
- **GAIP-2030**: Principles for trustworthy healthcare AI.

## 4. Performance Specifications

- **Retrieval Latency**: < 5ms (Cached)
- **Verification Overhead**: ~50-100ms
- **Throughput**: 30+ RPS (Local M2/M3 or equivalent)
