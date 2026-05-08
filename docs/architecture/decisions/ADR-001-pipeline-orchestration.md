# ADR 001: Pipeline Orchestration Role

## Status
Accepted (v0.1.0a2)

## Context
The repository contains a top-level `sovereign_ai/pipeline.py` which currently manages the primary flow of data between retrieval, governance, and verification. However, the C4 architecture diagram implies a decoupled container-to-container flow.

## Decision
We will treat `pipeline.py` as the **Central Orchestrator** for the stack in its current alpha state. 

## Rationale
- **MVP Simplicity**: A single orchestrator is easier to debug and test than fully decoupled micro-services during the Research Preview phase.
- **Synchronous Bottleneck**: While containers 1–4 appear separate, they currently execute within a unified async event loop managed by `pipeline.py`.

## Future Refactor (Phase 6)
The goal is to refactor `pipeline.py` into a thin wrapper over a **ForensicMiddleware** chain, allowing for true separation of concerns and middleware-based injection of audit and verification logic.
