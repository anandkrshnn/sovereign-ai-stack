# ZK Agent Attestation

Reference implementation of the **Prove-Transform-Verify (PTV)** authorization
model from the Sovereign AI Stack.

## What This Does

An agent proves a patient meets clinical eligibility criteria (e.g., age ≥ 18)
using a **Zero-Knowledge Range Proof** — without transmitting the patient's
actual age or any raw health record to the central federation hub.

This is the core mechanism enabling **Zero-Egress Sovereign Healthcare**:
the verifier confirms the result is correct without ever seeing the input data.

## Structure
zk-agent-attestation/
├── circuits/
│ ├── agent_prover.circom ← ZK circuit (range proof)
│ └── compile.sh ← End-to-end Groth16 build pipeline
└── benchmarks/
└── RESULTS.md ← Performance evidence (<200ms on NUC 12)

text

## Quick Start

```bash
npm install -g snarkjs circom
cd circuits
bash compile.sh
```

## NIST Reference

This implementation directly supports:
> **NIST NCCoE Public Comment** — *Accelerating the Adoption of Software
> and AI Agent Identity and Authorization*, March 2026
