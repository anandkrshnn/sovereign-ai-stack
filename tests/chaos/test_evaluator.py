import pytest
from sovereign_ai.verify import SovereignEvaluator, Config

def test_config_defaults():
    config = Config()
    assert config.model_name == "Qwen/Qwen2.5-1.5B-Instruct"
    assert config.temperature == 0.0

@pytest.mark.skip(reason="Requires GPU/Model download")
def test_evaluation_flow():
    evaluator = SovereignEvaluator()
    query = "Test query"
    context = "Test context"
    answer = "Test answer"
    
    result = evaluator.evaluate(query, context, answer)
    assert "grounding_score" in result
    assert "passed" in result
