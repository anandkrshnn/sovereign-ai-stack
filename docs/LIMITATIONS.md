# Sovereign AI Stack: Limitations

> **Status:** Alpha / Research Preview
> This document honestly outlines the current architectural constraints of the framework.

## 1. NLI Gate Latency Overhead
The `NLIAdaptiveGate` relies on a local instance of `cross-encoder/nli-deberta-v3-base`. 
- Even when running asynchronously via threadpools (`asyncio.to_thread`), this gate adds approximately **15ms to 50ms of overhead** per evaluated generation on modern hardware (e.g., RTX 4090). 
- On CPU-only environments, this overhead can spike significantly. It is currently unsuitable for sub-10ms high-frequency trading or real-time gaming agent loops.

## 2. Agent Sub-Systems are Basic
While the architecture integrates a `LocalPermissionBroker` and `AuditChainManager`, the core autonomous agent logic (`core_loop.py`) is a very standard **ReAct (Reasoning and Acting)** loop. 
- It is not an AGI. 
- It can handle multi-step tool use, but context degradation over 10+ turns is noticeable when using smaller models (e.g., Llama-3-8B).

## 3. Hardware Attestation is Local-First
The `TPM2LinuxAnchor` currently verifies PCR state measurements *locally* on the Linux machine where the agent runs. 
- We do not currently provide a robust **Remote Attestation (RATS)** microservice out of the box. 
- Using this in a multi-tenant cloud environment without custom integration into your cloud provider's Key Management Service (KMS) or confidential computing enclave (e.g., AWS Nitro, GCP Confidential VMs) provides a diminished security guarantee.

## 4. Single-Node SQLite Storage
The vector storage and relational context memory rely heavily on local SQLite and LanceDB instances.
- There is no distributed database clustering configured out of the box.
- Multi-node scaling is not currently supported without significant manual architectural changes.
