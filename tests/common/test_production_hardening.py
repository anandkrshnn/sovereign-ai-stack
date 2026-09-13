import pytest

from sovereign_ai.common.hardware_trust import HardwareTrustError, get_secure_anchor
from sovereign_ai.verify.config import Config
from sovereign_ai.verify.evaluator import SovereignEvaluator


def test_production_rejects_simulator(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_ENV", "production")
    monkeypatch.delenv("SOVEREIGN_ALLOW_SIMULATOR", raising=False)
    with pytest.raises(HardwareTrustError):
        get_secure_anchor("test-tenant", backend="mock")


def test_simulator_requires_explicit_opt_in_only_in_production(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SOVEREIGN_ENV", "production")
    monkeypatch.setenv("SOVEREIGN_ALLOW_SIMULATOR", "true")
    anchor = get_secure_anchor("test-tenant", backend="mock")
    assert not anchor.is_hardware


def test_consistency_guards_reject_new_numeric_claims():
    assert SovereignEvaluator._has_numeric_or_entity_mismatch(
        "The retention period is 7 years.", "The retention period is 9 years."
    )
    assert not SovereignEvaluator._has_numeric_or_entity_mismatch(
        "The retention period is 7 years.", "The retention period is 7 years."
    )


def test_config_env_limits(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_MAX_ANSWER_CHARS", "100")
    assert Config.from_env().max_answer_chars == 100
