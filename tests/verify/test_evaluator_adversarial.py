"""
tests/verify/test_evaluator_adversarial.py
------------------------------------------
Adversarial test suite for the SovereignEvaluator grounding judge.

These tests verify that the NLI judge does the right thing on:
  - clearly grounded answers (should PASS)
  - deliberate hallucinations (should FAIL / be blocked)
  - partial hallucinations (should FAIL — the gate is strict)
  - empty / edge-case inputs (fail-safe behaviour)

IMPORTANT: These tests load the real NLI model and require
~400 MB of disk space + network access on first run.

To run only this suite:
    pytest tests/verify/test_evaluator_adversarial.py -v

To skip if the model is not cached (CI without network):
    pytest tests/verify/test_evaluator_adversarial.py -v -m "not requires_model"

Marker used: @pytest.mark.requires_model
"""

import pytest
from sovereign_ai.verify.evaluator import SovereignEvaluator
from sovereign_ai.verify.config import Config


# ---------------------------------------------------------------------------
# Shared fixture — loaded once per session to avoid reloading the model
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def evaluator():
    """Real NLI evaluator — loads the cross-encoder model once per session."""
    config = Config(
        grounding_threshold=0.85,
        faithfulness_threshold=0.90,
    )
    ev = SovereignEvaluator(config=config)
    yield ev
    ev.unload()


# ---------------------------------------------------------------------------
# Clearly grounded answers — should PASS
# ---------------------------------------------------------------------------

class TestGroundedAnswers:
    """Answers that are directly supported by the provided context."""

    @pytest.mark.requires_model
    def test_direct_restatement_passes(self, evaluator):
        """An answer that directly restates a fact from context should pass."""
        context = (
            "Aspirin should not be given to children under 16 years old due to "
            "the risk of Reye's syndrome."
        )
        query = "Can aspirin be given to children?"
        answer = "Aspirin should not be given to children under 16 due to the risk of Reye's syndrome."

        result = evaluator.evaluate(query, context, answer)
        assert result["passed"] is True, (
            f"Expected grounded answer to pass. Scores: {result}"
        )
        assert result["grounding_score"] >= 0.85

    @pytest.mark.requires_model
    def test_paraphrase_passes(self, evaluator):
        """A paraphrase of the context (no new facts added) should pass."""
        context = (
            "The data retention period for financial audit logs is 7 years under "
            "the Companies Act 2013."
        )
        query = "How long must financial audit logs be retained?"
        answer = "Financial audit logs must be kept for 7 years, as required by the Companies Act 2013."

        result = evaluator.evaluate(query, context, answer)
        assert result["passed"] is True, (
            f"Expected paraphrase to pass. Scores: {result}"
        )

    @pytest.mark.requires_model
    def test_conservative_answer_passes(self, evaluator):
        """An answer that is a strict subset of the context should pass."""
        context = (
            "Under the DPDP Act 2023, data principals have the right to access, "
            "correct, and erase their personal data. Consent must be freely given, "
            "specific, informed, and unambiguous."
        )
        query = "What rights do data principals have under DPDP?"
        answer = "Data principals have the right to access, correct, and erase their personal data."

        result = evaluator.evaluate(query, context, answer)
        assert result["passed"] is True, (
            f"Expected conservative subset answer to pass. Scores: {result}"
        )


# ---------------------------------------------------------------------------
# Deliberate hallucinations — must FAIL and be BLOCKED
# ---------------------------------------------------------------------------

class TestHallucinations:
    """
    Answers that contain facts not present in — or contradicted by — the context.
    These MUST be blocked by the gate (passed=False).
    """

    @pytest.mark.requires_model
    def test_contradicted_fact_fails(self, evaluator):
        """
        Answer contradicts the context directly.
        CRITICAL: this is the core adversarial case. If the gate passes this,
        the verifier is broken.
        """
        context = (
            "Aspirin should not be given to children under 16 years old due to "
            "the risk of Reye's syndrome."
        )
        query = "Can aspirin be given to children?"
        # Deliberate contradiction: says the opposite of the context
        answer = "Aspirin is safe for children of all ages and is commonly prescribed for fever."

        result = evaluator.evaluate(query, context, answer)
        assert result["passed"] is False, (
            f"CRITICAL: contradicted fact was NOT blocked. Scores: {result}\n"
            "The grounding gate failed to catch a direct contradiction."
        )
        assert result["grounding_score"] < 0.85, (
            f"Grounding score too high for a contradicted answer: {result['grounding_score']}"
        )

    @pytest.mark.requires_model
    def test_fabricated_statistic_fails(self, evaluator):
        """Answer invents a number not present in the context."""
        context = (
            "LanceDB supports approximate nearest neighbour search using IVF-PQ indexing."
        )
        query = "What indexing does LanceDB use?"
        # Hallucinated statistic
        answer = "LanceDB uses IVF-PQ indexing and achieves 99.8% recall at 1ms latency."

        result = evaluator.evaluate(query, context, answer)
        assert result["passed"] is False, (
            f"Fabricated statistic was not blocked. Scores: {result}"
        )

    @pytest.mark.requires_model
    def test_out_of_scope_claim_fails(self, evaluator):
        """Answer brings in facts entirely absent from the context."""
        context = (
            "The hypertension protocol recommends lifestyle modification as first-line "
            "treatment including dietary sodium reduction and regular exercise."
        )
        query = "What is the first-line treatment for hypertension?"
        # Hallucinated drug name not in context
        answer = (
            "First-line treatment is lifestyle modification, and if that fails, "
            "ACE inhibitors such as ramipril at 5mg daily should be started."
        )

        result = evaluator.evaluate(query, context, answer)
        assert result["passed"] is False, (
            f"Out-of-scope drug claim was not blocked. Scores: {result}"
        )

    @pytest.mark.requires_model
    def test_empty_context_fails(self, evaluator):
        """With no context, any answer should fail the grounding check."""
        context = ""
        query = "What is the data retention period?"
        answer = "Data must be retained for 7 years."

        result = evaluator.evaluate(query, context, answer)
        assert result["passed"] is False, (
            f"Answer against empty context was not blocked. Scores: {result}"
        )

    @pytest.mark.requires_model
    def test_irrelevant_context_fails(self, evaluator):
        """Context about a completely different topic should not ground the answer."""
        context = "The Eiffel Tower is located in Paris and was built in 1889."
        query = "What is the blood pressure threshold for hypertension?"
        answer = "Hypertension is defined as blood pressure above 140/90 mmHg."

        result = evaluator.evaluate(query, context, answer)
        assert result["passed"] is False, (
            f"Answer with irrelevant context was not blocked. Scores: {result}"
        )


# ---------------------------------------------------------------------------
# Partial hallucinations — should also FAIL (gate is strict)
# ---------------------------------------------------------------------------

class TestPartialHallucinations:
    """
    Answers that mix grounded facts with fabricated additions.
    The gate must be strict: partial hallucination = blocked.
    """

    @pytest.mark.requires_model
    def test_grounded_plus_invented_detail_fails(self, evaluator):
        """
        First half of the answer is grounded; second half is invented.
        A strict gate must catch the added fabrication.
        """
        context = (
            "Under SOC 2 Type II, audit logs must be retained for a minimum of "
            "12 months and must be protected from unauthorised modification."
        )
        query = "What are the audit log requirements under SOC 2 Type II?"
        # The 12-month and tampering parts are grounded; the "automated alerts" part is not.
        answer = (
            "Audit logs must be retained for 12 months and protected from modification. "
            "Additionally, automated real-time alerts must be configured for any access anomalies."
        )

        result = evaluator.evaluate(query, context, answer)
        assert result["passed"] is False, (
            f"Partial hallucination (grounded + invented) was not blocked. Scores: {result}"
        )


# ---------------------------------------------------------------------------
# Score output structure
# ---------------------------------------------------------------------------

class TestOutputSchema:
    """The evaluate() return dict must always have the correct shape."""

    @pytest.mark.requires_model
    def test_output_keys_present(self, evaluator):
        result = evaluator.evaluate("query", "some context text", "some answer")
        assert set(result.keys()) == {
            "grounding_score", "faithfulness_score", "overall_score", "passed"
        }

    @pytest.mark.requires_model
    def test_scores_in_range(self, evaluator):
        result = evaluator.evaluate("query", "context", "answer")
        for key in ("grounding_score", "faithfulness_score", "overall_score"):
            assert 0.0 <= result[key] <= 1.0, f"{key} out of [0,1]: {result[key]}"

    @pytest.mark.requires_model
    def test_overall_is_mean(self, evaluator):
        result = evaluator.evaluate("query", "context text", "answer text")
        expected = round(
            (result["grounding_score"] + result["faithfulness_score"]) / 2, 4
        )
        assert abs(result["overall_score"] - expected) < 1e-4
