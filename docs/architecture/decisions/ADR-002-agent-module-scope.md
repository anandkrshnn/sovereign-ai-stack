# ADR 002: Agent Module Scope

## Status
Accepted (v0.1.0a2)

## Context
The directory `sovereign_ai/agent/` exists in the codebase but was missing from the initial architectural diagrams. This module is intended to handle autonomous task execution and resource management.

## Decision
The `agent/` module is defined as the **Agent Broker** within the stack. It sits between the `Bridge` (Interaction) and the `Policy Engine` (Governance).

## Rationale
- **Separation of Intents**: The `Bridge` handles API-compatible requests, while the `Agent Broker` manages long-running task state, resource quotas, and agentic reasoning before a governance check is triggered.

## Consequences
- The `Agent Broker` must be subject to the same **Airlock** verification as standard RAG queries to ensure that agent-generated actions are grounded in the same security policy.
