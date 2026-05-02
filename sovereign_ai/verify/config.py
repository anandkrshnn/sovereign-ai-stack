from dataclasses import dataclass


@dataclass
class Config:
    # NLI cross-encoder model.
    # Default: cross-encoder/nli-deberta-v3-base  (~400 MB, CPU-feasible, ~50ms/call)
    # Lighter alternative: cross-encoder/nli-deberta-v3-small (~180 MB, ~25ms/call)
    model_name: str = "cross-encoder/nli-deberta-v3-base"

    # Pass/fail thresholds — must both be met (conjunction, not OR).
    grounding_threshold: float = 0.85
    faithfulness_threshold: float = 0.90

    @classmethod
    def from_env(cls) -> "Config":
        return cls()
