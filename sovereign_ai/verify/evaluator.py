"""
sovereign_ai/verify/evaluator.py
---------------------------------
Grounding and faithfulness judge using a local NLI cross-encoder.

Architecture rationale
~~~~~~~~~~~~~~~~~~~~~~
The previous implementation used a generative causal LM (Qwen) and parsed
numeric scores from free-text output.  That approach has three problems for
a verification gate:

1. **Latency**: a 4-bit quantized generative model generating 128 tokens
   takes 500ms–5s per call, not <5ms.
2. **Reliability**: score extraction from free-text via regex is fragile;
   a model can emit the score value inside its reasoning rather than as
   a final verdict.
3. **Testability**: there is no way to write a deterministic adversarial
   test against free-text output.

This implementation replaces the generative judge with
``cross-encoder/nli-deberta-v3-base`` (or the lighter ``...-small`` variant),
a classification model trained specifically on SNLI + MultiNLI for
entailment/contradiction scoring.

Label order (from official model card, confirmed 2026-05-02):
    index 0 = contradiction
    index 1 = entailment      ← the score we use
    index 2 = neutral

Reference: https://huggingface.co/cross-encoder/nli-deberta-v3-base

Public API
~~~~~~~~~~
``SovereignEvaluator.evaluate(query, context, answer) -> dict``

The return schema is unchanged from the previous implementation so all
callers (pipeline, CLI, tests) work without modification.
"""

from __future__ import annotations

import logging
from typing import Dict

import torch
import torch.nn.functional as F
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from .config import Config

logger = logging.getLogger(__name__)

# Label order as documented in the model card for cross-encoder/nli-deberta-v3-*
_LABEL_ORDER = ["contradiction", "entailment", "neutral"]
_ENTAILMENT_IDX = _LABEL_ORDER.index("entailment")  # == 1


from .nli_calibration import PlattCalibrator, get_calibrator


class SovereignEvaluator:
    """
    Deterministic NLI-based grounding and faithfulness judge.

    Scores are entailment probabilities in [0.0, 1.0] derived from
    softmax over the three NLI logits, then calibrated using Platt Scaling.
    The gate passes when both grounding_score and faithfulness_score exceed
    their configured thresholds.
    """

    def __init__(self, config: Config | None = None) -> None:
        self.config = config or Config()
        self.tokenizer: AutoTokenizer | None = None
        self.model: AutoModelForSequenceClassification | None = None
        self.calibrator: PlattCalibrator | None = None
        self._load_model()
        self._load_calibrator()

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        model_name = self.config.model_name
        logger.info("Loading NLI judge model: %s", model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
        )
        self.model.eval()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = self.model.to(device)
        logger.info("NLI judge loaded on %s", device)

    def _load_calibrator(self) -> None:
        """Loads a calibrator for the current model."""
        self.calibrator = get_calibrator(self.config.model_name)
        logger.info("NLI calibrator loaded for %s", self.config.model_name)

    # ------------------------------------------------------------------
    # Public API (schema unchanged from previous implementation)
    # ------------------------------------------------------------------

    def evaluate(self, query: str, context: str, answer: str) -> Dict:
        """
        Score grounding and faithfulness of *answer* given *context*.

        Optimized v0.1.0a5: Batch inference for grounding and faithfulness.
        Now includes Platt Calibration for higher precision.
        """
        premises = [context, f"{query}\n\n{context}"]
        hypotheses = [answer, answer]

        raw_probs = self._batch_entailment_probs(premises, hypotheses)

        # Apply calibration
        grounding_score = self.calibrator.calibrate(raw_probs[0])
        faithfulness_score = self.calibrator.calibrate(raw_probs[1])

        passed = bool(
            grounding_score >= self.config.grounding_threshold
            and faithfulness_score >= self.config.faithfulness_threshold
        )

        return {
            "grounding_score": round(grounding_score, 4),
            "faithfulness_score": round(faithfulness_score, 4),
            "overall_score": round((grounding_score + faithfulness_score) / 2, 4),
            "passed": passed,
            "raw_scores": [round(p, 4) for p in raw_probs],
        }

    def evaluate_with_threshold(self, query: str, context: str, answer: str, threshold: float = 0.85) -> Dict:
        """
        Evaluate and strictly enforce a cutoff threshold. If scores fall below,
        it logs the failure to low_confidence.log and fails-closed.
        """
        result = self.evaluate(query, context, answer)
        
        grounding = result["grounding_score"]
        faithfulness = result["faithfulness_score"]
        
        passed = grounding >= threshold and faithfulness >= threshold
        result["passed"] = passed
        
        if not passed:
            log_msg = (
                f"REJECTED: threshold={threshold} | "
                f"grounding={grounding} | faithfulness={faithfulness} | "
                f"query='{query}' | answer='{answer}'"
            )
            # Log to dedicated low_confidence.log
            with open("low_confidence.log", "a", encoding="utf-8") as f:
                f.write(log_msg + "\n")
            logger.warning(log_msg)
            
        return result
            
    async def evaluate_async(self, query: str, context: str, answer: str) -> Dict:
        """
        Asynchronously score grounding and faithfulness, releasing the GIL
        via a threadpool. Critical for high-throughput pipeline integration.
        """
        import asyncio
        return await asyncio.to_thread(self.evaluate, query, context, answer)

    async def evaluate_with_threshold_async(self, query: str, context: str, answer: str, threshold: float = 0.85) -> Dict:
        """
        Asynchronously evaluate and strictly enforce a cutoff threshold.
        """
        import asyncio
        return await asyncio.to_thread(self.evaluate_with_threshold, query, context, answer, threshold)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _batch_entailment_probs(self, premises: list[str], hypotheses: list[str]) -> list[float]:
        """
        Run multiple NLI inference passes in a single batch and return entailment probabilities.
        """
        assert self.model is not None and self.tokenizer is not None

        inputs = self.tokenizer(
            premises,
            hypotheses,
            padding=True,
            truncation=True,
            max_length=512,
            return_tensors="pt",
        ).to(self.model.device)

        with torch.no_grad():
            logits = self.model(**inputs).logits  # shape: (N, 3)

        probs = F.softmax(logits, dim=-1)  # (N, 3)
        entailment_probs = probs[:, _ENTAILMENT_IDX].tolist()
        return [float(p) for p in entailment_probs]

    def _entailment_prob(self, premise: str, hypothesis: str) -> float:
        """Backward compatibility for single calls."""
        return self._batch_entailment_probs([premise], [hypothesis])[0]

    def unload(self) -> None:
        """Release GPU memory."""
        if self.model is not None:
            del self.model
            self.model = None
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            logger.info("NLI judge unloaded.")
