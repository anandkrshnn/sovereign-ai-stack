import pytest
from local_rag.schemas import Document, RAGResponse

def test_ask_with_results(rag_instance):
    doc = Document(doc_id="d1", source="s1", content="SQLite FTS5 is a full-text search engine.")
    rag_instance.retriever.ingest([doc])
    
    response = rag_instance.ask("SQLite FTS5")
    
    assert isinstance(response, RAGResponse)
    assert response.answer == "Mocked answer based on context."
    assert len(response.sources) > 0
    assert response.sources[0].doc_id == "d1"
    # Ensure generator was called
    rag_instance.generator.generate.assert_called_once()

def test_ask_fail_closed(rag_instance):
    # No documents ingested
    response = rag_instance.ask("Anything")
    
    assert "Insufficient Local Context" in response.answer
    assert len(response.sources) == 0
    # Ensure generator was NOT called
    rag_instance.generator.generate.assert_not_called()

def test_ask_streaming_mock(rag_instance):
    doc = Document(doc_id="d1", source="s1", content="Some context.")
    rag_instance.retriever.ingest([doc])
    
    stream = rag_instance.ask("context", stream=True)
    chunks = list(stream)
    
    assert "".join(chunks) == "Mocked streaming answer."
    rag_instance.generator.stream_generate.assert_called_once()

def test_ask_fail_closed_streaming(rag_instance):
    # No documents ingested
    stream = rag_instance.ask("Anything", stream=True)
    chunks = list(stream)
    
    assert "Insufficient Local Context" in "".join(chunks)
    assert rag_instance.generator.stream_generate.call_count == 0
