import pytest
from local_rag.schemas import Document
from local_rag.retriever import FTS5Retriever

def test_ingestion_and_counts(retriever, temp_db):
    doc = Document(doc_id="test1", source="test", content="This is a long test document about sovereign agents and RAG.")
    retriever.ingest([doc], chunk_size=20, chunk_overlap=0)
    
    conn = retriever.store.conn
    doc_count = conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    chunk_count = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    fts_count = conn.execute("SELECT COUNT(*) FROM chunks_fts").fetchone()[0]
    
    assert doc_count == 1
    assert chunk_count > 1
    assert fts_count == chunk_count

def test_search_ranking(retriever):
    docs = [
        Document(doc_id="d1", source="s1", content="Apple fruit nutrition facts."),
        Document(doc_id="d2", source="s2", content="How to bake an apple pie recipe.")
    ]
    retriever.ingest(docs)
    
    # "fruit" should rank d1 first
    results = retriever.search("fruit")
    assert results[0].doc_id == "d1"
    
    # "pie" should rank d2 first
    results = retriever.search("pie")
    assert results[0].doc_id == "d2"

def test_snippet_generation(retriever):
    doc = Document(doc_id="d1", source="s1", content="The quick brown fox jumps over the lazy dog.")
    retriever.ingest([doc])
    
    results = retriever.search("quick brown")
    assert "[result]" in results[0].text
    assert "quick" in results[0].text.lower()
    assert "brown" in results[0].text.lower()

def test_no_results(retriever):
    results = retriever.search("nonexistentword")
    assert len(results) == 0
