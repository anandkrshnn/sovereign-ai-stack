# 🛠️ Sovereign AI Stack — Contributor Onboarding Guide (v2.0 Pillars)

Welcome! This guide is designed to get you up to speed quickly on local development, directory structures, testing frameworks, and implementation patterns for the five core security and architectural pillars of the **Sovereign AI Stack v2.0**.

---

## 💻 1. Global Setup & Dependencies

Before diving into any of the specific pillars, set up your local development environment:

```bash
# 1. Clone the repository
git clone https://github.com/anandkrshnn/sovereign-ai-stack
cd sovereign-ai-stack

# 2. Install dependencies in editable mode with all extras
pip install -e ".[dev,agent,verify]"

# 3. Verify the installation by running the test suite
pytest tests/ -m "not requires_model" -v
```

---

## 🧩 2. Deep Dives into the 5 Pillars

### 🔒 Pillar 1: Attestation Isolation
*   **Goal**: Refactor the attestation checking engine from the main agent process into an isolated secure enclave microservice.
*   **Key Files**:
    *   [base.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/common/hardware_trust/base.py) — SecureAnchor abstract interface.
    *   [mock_sim.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/common/hardware_trust/mock_sim.py) — Mock simulation framework.
*   **Recommended Stack**: `grpcio`, `grpcio-tools`, `protobuf`
*   **Implementation Guide**:
    1.  Create a new directory `sovereign_ai/services/attestation/` for the microservice.
    2.  Write a Protobuf definition (`attestation.proto`) specifying the `AttestationVerifier` service interface.
    3.  Generate python gRPC stubs:
        ```bash
        python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. attestation.proto
        ```
    4.  Implement a wrapper client class in `sovereign_ai/common/hardware_trust/enclave_client.py` that inherits from [SecureAnchor](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/common/hardware_trust/base.py) and communicates with the gRPC microservice.
*   **Verification**:
    *   Add tests verifying connection retry and fail-closed security properties to `tests/integration/test_enclave_isolation.py`.

---

### 🔑 Pillar 2: TPM-Sealed Keys
*   **Goal**: Seal SQLCipher database encryption keys in physical TPM 2.0 NVRAM, unsealing them only when Platform Configuration Registers (PCRs) match a trusted state.
*   **Key Files**:
    *   [tpm_signer.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/agent/tpm_signer.py) — Current hardware-bound TPM signing logic.
    *   [tpm2_linux.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/common/hardware_trust/tpm2_linux.py) — Linux TPM2 implementation.
    *   [store.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/rag/store.py) — SQLCipher database initialization.
*   **Recommended Stack**: `tpm2-pytss`, `sqlcipher3-wheels`
*   **Implementation Guide**:
    1.  Extend the [SecureAnchor](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/common/hardware_trust/base.py) abstract methods `seal_key` and `unseal_key`.
    2.  In [tpm2_linux.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/common/hardware_trust/tpm2_linux.py), implement the TPM2 API calls (`ESYS_TR`, `Fapi`) to seal the database key to PCR states 0–7 and 11.
    3.  In [store.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/rag/store.py), update the SQLite connection factory to retrieve the unsealed key from the TPM provider during initialization instead of raw environment variables.
*   **Verification**:
    *   Run `pytest tests/test_encryption.py` to ensure SQLCipher encryption and re-keying operations execute successfully.
    *   For local testing without physical TPM hardware, use the mock simulator key directories: `.tpm_sim/`.

---

### 📥 Pillar 3: Async Audit Ledger
*   **Goal**: Move the forensic audit ledger recomputation and signing operations out-of-band to prevent bottlenecking user response times.
*   **Key Files**:
    *   `sovereign_ai/agent/forensics/` — Forensic logging files.
    *   [pipeline.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/pipeline.py) — Core pipeline execution.
*   **Recommended Stack**: `asyncio`, `boto3` (for S3 Object Lock/WORM), or local filesystems.
*   **Implementation Guide**:
    1.  Create an asynchronous background worker pool in `sovereign_ai/agent/forensics/worker.py` using `asyncio.Queue`.
    2.  Decouple the write pipeline in [pipeline.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/pipeline.py): rather than waiting for Merkle root computation and key signing, put the audit records into the queue.
    3.  The background worker should batch events, calculate the Merkle tree periodically, and upload the signed Merkle checkpoint to a Write-Once-Read-Many (WORM) storage backend (e.g. AWS S3 with Object Lock or local filesystem with read-only permissions).
*   **Verification**:
    *   Run `python benchmark.py` to verify the latency reduction of the request path.
    *   Run concurrency tests in `tests/test_audit_chain.py` to check for data-race safety and trace consistency.

---

### 🌐 Pillar 4: Ontology Policy Engine
*   **Goal**: Upgrade the policy engine from primitive prefix-matching to a rich, ontology-driven model supporting transitives, class hierarchies, and SPARQL conflict verification.
*   **Key Files**:
    *   [policy_z3.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/verify/policy_z3.py) — Z3 SMT solver verification framework.
    *   [docs/GOVERNANCE_MODEL.md](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/docs/GOVERNANCE_MODEL.md) — Governance and ABAC layout definitions.
*   **Recommended Stack**: `rdflib`, `z3-solver`
*   **Implementation Guide**:
    1.  Create the base RDF/OWL policy schema in `sovereign_ai/verify/ontology/policy_schema.ttl`.
    2.  Write an RDF parser in `sovereign_ai/verify/ontology_parser.py` that translates OWL hierarchies (e.g. `PrincipalClass`, `SubRoleOf`) into boolean formulas for the Z3 SMT Solver.
    3.  Update [policy_z3.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/verify/policy_z3.py) to check for transitive relationships and logical overlaps using SPARQL queries or Z3 constraints.
*   **Verification**:
    *   Add tests to `tests/verify/test_policy_z3.py` asserting that role inheritance, wildcard expansion, and nested conflict detection work as expected.

---

### 🧠 Pillar 5: Adversarial NLI Gate
*   **Goal**: Retrain and fine-tune the NLI gate to defend the system against jailbreaks and negation-based evasion vectors.
*   **Key Files**:
    *   [nli_calibration.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/verify/nli_calibration.py) — Platt scaling and NLI probability calibration.
    *   [evaluator.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/verify/evaluator.py) — Grounding evaluator pipeline.
*   **Recommended Stack**: `transformers`, `torch`, `scikit-learn`
*   **Implementation Guide**:
    1.  Obtain training datasets (like ANLI and SNLI-Hard) and format them into entailment, contradiction, and neutral classification formats.
    2.  Use the script in `sovereign_ai/verify/train_nli.py` to fine-tune the base `deberta-v3-base` model.
    3.  Implement a joint ensemble voter inside `sovereign_ai/verify/ensemble.py` combining the model's confidence scores (calibrated via [nli_calibration.py](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/sovereign_ai/verify/nli_calibration.py)) with a regex/keyword check.
*   **Verification**:
    *   Run `pytest tests/verify/test_evaluator_adversarial.py -m requires_model` to validate the gate's robustness against jailbreaks and negation patterns.

---

## 🧪 3. Running Local Benchmarks & Certification

Every major change to the security pillars must undergo benchmarking and formal certification:

*   **To run the NLI judge latency benchmarks:**
    ```bash
    python benchmark.py
    ```
*   **To run chaos/security certification tests:**
    ```bash
    pytest tests/certification/ --sovereign-cert -v
    ```
*   **To regenerate the certification report**:
    ```bash
    python -m tests.certification.generate_report
    ```
    This will update the [CERTIFICATION.md](file:///c:/Users/Monika/Documents/GitHub/sovereign-ai-stack/CERTIFICATION.md) report detailing your test scores for Tenant Isolation, Policy Fail-Closed, Cache Isolation, and Audit Integrity.
