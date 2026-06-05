# LIMITATIONS: Sovereign AI Stack (v2.0)

## Technical Limitations of the NLI Gate

The Natural Language Inference (NLI) Gate relies on a cross-encoder model to verify text. It is a probabilistic filter, not a deterministic rule engine. The following are fundamental architectural limitations:

### 1. Syntactic Mimicry
The gate correlates structural similarity with entailment. If a hallucinated response closely mimics the noun phrases and syntax of the source context, the model typically approves it with high confidence (>90%). It relies on pattern matching rather than formal logic reasoning.

### 2. Numerical and Entity Blindness
In contexts with dense terminology (e.g., financial documents or medical records), the cross-encoder frequently fails to identify swapped numbers or entities. A generated answer altering "$400M" to "$40M" may pass if the surrounding boilerplate is identical. Secondary exact-match verification (like regex or named entity extraction) is strictly required for quantitative data.

### 3. Multi-Hop Logical Negation
The model struggles to correctly process nested logical negations (e.g., "It is not the case that X is absent"). Such constructs cause embedding distortion, leading to unreliable confidence scores that bypass standard rejection thresholds.

### 4. Out-of-Distribution Vulnerability
The underlying model (DeBERTa v3) is trained on standard NLI datasets (SNLI/MultiNLI). It lacks domain-specific vocabularies. When evaluating complex cryptographic specifications or proprietary biochemical research, confidence scores hold minimal predictive value.

### 5. Context Truncation
Input arrays (`query + context + answer`) exceeding 512 tokens are silently truncated. If critical grounding information resides at the end of the context, the gate may incorrectly reject a faithful answer or approve an ungrounded one based on incomplete data.

### Deployment Requirement
The NLI Gate cannot operate as a standalone security boundary. It must be paired with strict confidence thresholding (>= 0.85), exact-match safety nets, and human oversight for high-risk deployments.

## Technical Limitations of the Audit Chain

The forensic audit chain provides tamper-evident append-only logging using cryptographic hashes, Ed25519 signatures, and Merkle Trees. The following are fundamental architectural limitations:

### 1. Proof Availability Delay
The `get_audit_proof(audit_id)` function relies on a block being sealed into a `MERKLE_CHECKPOINT`. Until the configured checkpoint interval (e.g., 10 events) is reached, recent events cannot yield a valid Merkle root or hardware attestation quote.

### 2. State Rollback Attacks
While tampering with an existing record breaks the hash chain and Merkle inclusion proofs, an attacker with root access to the filesystem could delete the entire audit log or roll it back to a previous valid state. Prevention of rollback attacks relies entirely on out-of-band monitoring or remote replication of checkpoints.

### 3. Key Compromise
The integrity of the chain relies on the hardware anchor (TPM/HSM) or the software signing key. If the underlying host environment is severely compromised such that the signing key is extracted or arbitrary payloads can be injected into the signing module, the attacker can forge a mathematically valid alternate history.

### 4. Exclusion Proofs
The current implementation supports standard inclusion proofs but does not feature sorted Sparse Merkle Trees. Exclusion (proving a specific event did not occur) is handled by linear search and raising an exception if absent, rather than via O(log N) cryptographic non-inclusion proofs.
