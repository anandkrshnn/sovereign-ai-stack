from dataclasses import dataclass
from pathlib import Path

@dataclass
class Config:
    model_name: str = "Qwen/Qwen2.5-1.5B-Instruct"   # Fast local judge
    load_in_4bit: bool = True
    max_new_tokens: int = 256
    temperature: float = 0.0   # Deterministic evaluation
    top_p: float = 0.9

    grounding_threshold: float = 0.85
    faithfulness_threshold: float = 0.90

    @classmethod
    def from_env(cls):
        return cls()
