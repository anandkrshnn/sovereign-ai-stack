import os
from dataclasses import dataclass


@dataclass
class Config:
    # NLI cross-encoder model.
    # Default: cross-encoder/nli-deberta-v3-base  (~400 MB, CPU-feasible, ~50ms/call)
    # Lighter alternative: cross-encoder/nli-deberta-v3-small (~180 MB, ~25ms/call)
    model_name: str = "cross-encoder/nli-deberta-v3-base"

    grounding_threshold: float = 0.85
    faithfulness_threshold: float = 0.85
    max_input_chars: int = 100_000
    max_answer_chars: int = 20_000
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            model_name=os.getenv("SOVEREIGN_NLI_MODEL", cls.model_name),
            grounding_threshold=float(os.getenv("SOVEREIGN_GROUNDING_THRESHOLD", "0.85")),
            faithfulness_threshold=float(os.getenv("SOVEREIGN_FAITHFULNESS_THRESHOLD", "0.85")),
            max_input_chars=int(os.getenv("SOVEREIGN_MAX_INPUT_CHARS", "100000")),
            max_answer_chars=int(os.getenv("SOVEREIGN_MAX_ANSWER_CHARS", "20000")),
            timeout_seconds=float(os.getenv("SOVEREIGN_NLI_TIMEOUT_SECONDS", "30")),
        )
