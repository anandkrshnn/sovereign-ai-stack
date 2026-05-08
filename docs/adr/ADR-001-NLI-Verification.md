# ADR 001: NLI-Based Grounding Verification

## Status
Accepted (v0.1.0a2)

## Context
Standard RAG pipelines often rely on generative LLMs to "judge" their own output. This introduces probabilistic failure modes where the judge may hallucinate or fail to detect subtle contradictions. Regulated industries (Healthcare, Finance) require a more deterministic approach to grounding.

## Decision
We will use a **Natural Language Inference (NLI) Cross-Encoder** (specifically `DeBERTa-v3-base`) as the primary verification engine.

## Rationale
- **Deterministic Scoring**: NLI models output a discrete probability for `entailment`, `neutral`, and `contradiction`.
- **Latency**: Cross-encoders are significantly faster (~50ms) than generative judges (~1000ms+).
- **Interpretability**: The score maps directly to the logical relationship between the context and the claim, rather than a subjective LLM "reasoning" block.

## Consequences
- **Fixed Model**: The system is tethered to a specific NLI model for consistent scoring.
- **Context Length**: Verification latency scales with the number of claims; massive responses require chunked verification.
- **Statistical Tuning**: Requires empirical calibration of the 0.8-0.9 threshold to balance precision and recall.
