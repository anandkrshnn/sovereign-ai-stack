import pytest
from sovereign_ai.verify import SovereignEvaluator, Config

def test_config_defaults():
    config = Config()
    assert config.model_name == "cross-encoder/nli-deberta-v3-base"
    assert config.grounding_threshold == 0.85

@pytest.mark.requires_model
def test_evaluation_flow():
    evaluator = SovereignEvaluator()
    query = "Is aspirin safe for children?"
    context = "Aspirin should not be given to children under 16 due to Reye's syndrome risk."
    answer = "No, aspirin is not safe for children under 16."
    
    result = evaluator.evaluate(query, context, answer)
    assert "grounding_score" in result
    assert "passed" in result
    assert isinstance(result["passed"], bool)
