import pytest
import json
from pathlib import Path
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from local_rag.cli import app
from local_rag.main import LocalRAG

runner = CliRunner()

@pytest.fixture
def mock_docs_file(tmp_path):
    f = tmp_path / "docs.json"
    content = [{"doc_id": "d1", "content": "Sample content", "source": "src1"}]
    f.write_text(json.dumps(content))
    return f

def test_cli_ingest(temp_db, mock_docs_file):
    with patch("local_rag.cli.LocalRAG") as mock_rag_cls:
        mock_rag = mock_rag_cls.return_value
        result = runner.invoke(app, ["ingest", str(mock_docs_file), "--db", temp_db])
        
        assert result.exit_code == 0
        assert "Successfully ingested" in result.stdout
        mock_rag.retriever.ingest.assert_called_once()

def test_cli_search(temp_db):
    with patch("local_rag.cli.LocalRAG") as mock_rag_cls:
        mock_rag = mock_rag_cls.return_value
        mock_rag.retriever.search.return_value = [] # No hits for test
        
        result = runner.invoke(app, ["search", "query", "--db", temp_db])
        
        assert result.exit_code == 0
        assert "No results found" in result.stdout
        mock_rag.retriever.search.assert_called_once()

def test_cli_stats(temp_db):
    result = runner.invoke(app, ["stats", "--db", temp_db])
    assert result.exit_code == 0
    assert "Database:" in result.stdout

def test_cli_ask_no_stream(temp_db):
    with patch("local_rag.cli.LocalRAG") as mock_rag_cls:
        mock_rag = mock_rag_cls.return_value
        mock_response = MagicMock()
        mock_response.answer = "The answer."
        mock_response.sources = []
        mock_rag.ask.return_value = mock_response
        
        result = runner.invoke(app, ["ask", "What is RAG?", "--db", temp_db])
        
        assert result.exit_code == 0
        assert "The answer." in result.stdout
        mock_rag.ask.assert_called_once()

def test_cli_ask_streaming(temp_db):
    with patch("local_rag.cli.LocalRAG") as mock_rag_cls:
        mock_rag = mock_rag_cls.return_value
        mock_rag.ask.return_value = iter(["Streaming ", "chunk."])
        
        result = runner.invoke(app, ["ask", "Streaming question?", "--db", temp_db, "--stream"])
        
        assert result.exit_code == 0
        # Rich Live output can be tricky to capture exactly, but we check if ask was called
        mock_rag.ask.assert_called_once()

def test_cli_ingest_not_found():
    result = runner.invoke(app, ["ingest", "nonexistent.json"])
    assert result.exit_code == 1
    assert "not found" in result.stdout

def test_cli_search_with_results(temp_db):
    with patch("local_rag.cli.LocalRAG") as mock_rag_cls:
        mock_rag = mock_rag_cls.return_value
        mock_result = MagicMock()
        mock_result.score = 1.0
        mock_result.doc_id = "d1"
        mock_result.text = "Found [result]text[/result]"
        mock_rag.retriever.search.return_value = [mock_result]
        
        result = runner.invoke(app, ["search", "query", "--db", temp_db])
        assert result.exit_code == 0
        assert "d1" in result.stdout
