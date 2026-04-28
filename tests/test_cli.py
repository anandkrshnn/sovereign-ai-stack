import pytest
import json
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch, MagicMock, AsyncMock

from sovereign_ai.cli import main as app

runner = CliRunner()

@pytest.fixture
def mock_docs_file(tmp_path):
    f = tmp_path / "docs.txt"
    f.write_text("Sample content for ingestion test.")
    return f

def test_cli_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Sovereign AI Stack v" in result.stdout

def test_cli_ingest(mock_docs_file):
    with patch("sovereign_ai.cli.SovereignPipeline") as mock_pipeline_cls:
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.ingest = AsyncMock()
        mock_pipeline.close = AsyncMock()
        
        result = runner.invoke(app, ["ingest", str(mock_docs_file), "--tenant", "test_tenant"])
        
        assert result.exit_code == 0
        assert "Ingested" in result.stdout

def test_cli_ask():
    with patch("sovereign_ai.cli.SovereignPipeline") as mock_pipeline_cls:
        mock_pipeline = mock_pipeline_cls.return_value
        mock_pipeline.ask = AsyncMock()
        mock_pipeline.close = AsyncMock()
        
        mock_response = MagicMock()
        mock_response.answer = "The sovereign answer."
        mock_response.metadata = {}
        mock_pipeline.ask.return_value = mock_response
        
        result = runner.invoke(app, ["ask", "What is the protocol?", "--principal", "doctor"])
        
        assert result.exit_code == 0
        assert "The sovereign answer." in result.stdout

def test_cli_audit_verify():
    # Patch where it is DEFINED, since it's imported locally in the function
    with patch("sovereign_ai.common.audit.SovereignAuditLogger") as mock_logger_cls:
        mock_logger = mock_logger_cls.return_value
        mock_logger.verify_integrity.return_value = True
        
        result = runner.invoke(app, ["audit", "verify", "--tenant", "test_tenant"])
        
        assert result.exit_code == 0
        assert "VALID" in result.stdout
