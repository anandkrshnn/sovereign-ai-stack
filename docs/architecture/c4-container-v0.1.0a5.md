# C4 Container Diagram: Sovereign AI Stack (v0.1.0a2)

> [!NOTE]
> **Orchestration Note**: In the current Alpha state, `pipeline.py` orchestrates the flow between containers 1–4. The target refactor is to move this into a decoupled `ForensicMiddleware` chain in Phase 6.

```mermaid
C4Container
    title Container Diagram for Sovereign AI Stack (v0.1.0a2)

    Person(user, "Authenticated Principal", "Internal user or automated agent.")

    System_Boundary(stack, "Sovereign AI Stack (Local-First)") {
        Container(bridge, "Sovereign Bridge", "Python/FastAPI", "OpenAI-compatible gateway & Tenant Routing.")
        Container(agent, "Agent Broker", "Python", "Task dispatch and resource quota management.")
        Container(policy, "ABAC Policy Engine", "Python", "Evaluates access rules before retrieval.")
        Container(airlock, "Ensemble Airlock", "DeBERTa-v3/Ensemble", "Deterministic NLI grounding & Safety verification.")
        Container(audit, "Forensic Audit Hub", "Merkle-Tree/Ed25519", "Asymmetric signing & Proof-of-Inclusion.")
        ContainerDb(storage, "Sovereign Storage", "SQLite/LanceDB", "Encrypted per-tenant vector & metadata silos.")
    }

    System_Ext(llm, "Local LLM / Ollama", "The generative engine (Host-integrated).")
    System_Ext(tpm, "TPM 2.0 / Enclave", "Hardware Root of Trust for key anchoring.")

    Rel(user, bridge, "Sends Query (JWT/API-Key)")
    Rel(bridge, agent, "Dispatches Task")
    Rel(agent, policy, "Validates Intent")
    Rel(policy, storage, "Queries filtered context")
    Rel(storage, airlock, "Feeds context for verification")
    Rel(llm, airlock, "Sends draft response")
    Rel(airlock, audit, "Sends verified event for signing")
    Rel(audit, tpm, "Anchors Merkle root")
    Rel(audit, user, "Returns response + Forensic Proof")
```

### 🛡️ Layered Sovereignty Matrix

| Layer | Component | Architect Value |
| :--- | :--- | :--- |
| **Layer 1: Interaction** | **Sovereign Bridge** | Prevents cross-principal data leakage at the entry point. |
| **Layer 2: Governance** | **ABAC Engine** | Ensures data is never leaked into the prompt context illegally. |
| **Layer 3: Verification** | **Ensemble Airlock** | Mitigates the "Black Box" failure mode of probabilistic LLMs. |
| **Layer 4: Forensics** | **Audit Hub** | Provides immutable evidence for regulatory compliance. |
