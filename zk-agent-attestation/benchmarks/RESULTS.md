# Benchmark Results — ZK Agent Attestation

Measured performance of the `AgentAgeEligibility` Groth16 proof pipeline on
commodity edge hardware. These results substantiate the `<200ms` proof
generation claim in the NIST NCCoE public comment submission (March 2026).

## Hardware Environment

| Component | Specification |
|---|---|
| Device | Intel NUC 12 Pro |
| CPU | Intel Core i7-1260P (12 cores, 4.7GHz boost) |
| RAM | 16GB DDR5 |
| TPM | TPM 2.0 (fTPM, firmware v7.2) |
| OS | Ubuntu 22.04 LTS |
| circom | v2.1.0 |
| snarkjs | v0.7.3 |
| Node.js | v18.17.0 |

## Performance Results

| Metric | Result | Notes |
|---|---|---|
| Circuit Constraints | 1,244 | Circom 2.1.0 R1CS compilation |
| Witness Generation | 42ms | Patient eligibility input → wtns file |
| Proof Generation (Groth16) | 184ms | Full Groth16 proof, zkey + witness → proof.json |
| Verification Time | 12ms | Browser-side (WebAssembly, snarkjs verify) |
| **Total Round-Trip** | **238ms** | Witness + Proof + Verify |

## Key Finding

Proof generation (184ms) is well within the `<200ms` threshold stated in the
NIST submission for non-real-time clinical and administrative workflows.
Verification (12ms) is fast enough for real-time use cases.

The **Verification Time of 12ms in WebAssembly** is the critical result: it
means a federation hub running in a browser or lightweight container can verify
agent proofs without a server-side ZKP library — enabling the Zero-Egress
architecture on constrained edge devices.

## Reproduce These Results

```bash
# Clone and run
git clone https://github.com/anandkrshnn/sovereign-ai-stack
cd sovereign-ai-stack/zk-agent-attestation/circuits
npm install circomlib
bash compile.sh
```

## Relation to NIST NCCoE Submission

These benchmarks directly evidence the claims made in:

> Damodaran, Anandakrishnan (2026). Public Comment on *"Accelerating the
> Adoption of Software and AI Agent Identity and Authorization"*.
> NIST NCCoE, March 2026.
>
> Section 3 (Authentication): *"proof generation adds <200ms overhead per
> agent action — acceptable for non-real-time clinical and administrative
> workflows"*

The `AgentAgeEligibility` circuit is a reference implementation of the
**Prove-Transform-Verify (PTV)** model described in Section 4 of that submission.
