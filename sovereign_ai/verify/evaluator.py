import torch
import re
from typing import Dict, Tuple
from transformers import AutoTokenizer, AutoModelForCausalLM
from .config import Config
from .prompts import GROUNDING_PROMPT, FAITHFULNESS_PROMPT

class SovereignEvaluator:
    def __init__(self, config: Config = None):
        self.config = config or Config()
        self.tokenizer = None
        self.model = None
        self._load_model()

    def _load_model(self):
        print(f"Loading sovereign judge {self.config.model_name}...")
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.config.model_name, trust_remote_code=True
        )
        
        quant_config = None
        if self.config.load_in_4bit:
            try:
                from transformers import BitsAndBytesConfig
                quant_config = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_compute_dtype=torch.float16,
                    bnb_4bit_quant_type="nf4"
                )
            except ImportError:
                print("Warning: bitsandbytes not found. Loading in full precision.")

        self.model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            torch_dtype="auto",
            device_map="auto",
            trust_remote_code=True,
            quantization_config=quant_config,
        )
        self.model.eval()

    def evaluate(self, query: str, context: str, answer: str) -> Dict:
        """Return grounding and faithfulness scores."""
        grounding_score = self._score_with_prompt(GROUNDING_PROMPT, query, context, answer)
        faithfulness_score = self._score_with_prompt(FAITHFULNESS_PROMPT, query, context, answer)

        return {
            "grounding_score": grounding_score,
            "faithfulness_score": faithfulness_score,
            "overall_score": round((grounding_score + faithfulness_score) / 2, 2),
            "passed": (
                grounding_score >= self.config.grounding_threshold and
                faithfulness_score >= self.config.faithfulness_threshold
            )
        }

    def _score_with_prompt(self, template: str, query: str, context: str, answer: str) -> float:
        prompt = template.format(query=query, context=context, answer=answer)
        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=128,   # Space for Reasoning + Score
                temperature=self.config.temperature,
                do_sample=False,
            )

        response = self.tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:], 
            skip_special_tokens=True
        ).strip()

        # Robust numeric extraction using tags [SCORE]x.x[/SCORE]
        # We look for the LAST occurrence to avoid numbers in reasoning
        matches = re.findall(r"\[SCORE\]\s*(\d+\.\d+|\d+)\s*\[/SCORE\]", response)
        if not matches:
            # Fallback to simple regex if tags missed
            matches = re.findall(r"(\d+\.\d+|\d+)", response)
            
        if matches:
            try:
                # Take the last match (usually the final score)
                score = float(matches[-1])
                return max(0.0, min(1.0, score))
            except ValueError:
                pass
        
        return 0.0   # Fail-closed

    def unload(self):
        if self.model is not None:
            del self.model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
