import os
import pytest
from pathlib import Path
from sovereign_ai.rag.main import LocalRAG
from sovereign_ai.rag.schemas import Document

# Gated by environment variable
RUN_SLOW = os.getenv("LOCAL_RAG_RUN_SLOW") == "1"

@pytest.mark.slow
@pytest.mark.skipif(not RUN_SLOW, reason="Set LOCAL_RAG_RUN_SLOW=1 to run real-model integration tests")
def test_ask_smoke_test(temp_db, tmp_path):
    """Real end-to-end smoke test using a tiny Qwen model."""
    # Use a temporary HF cache to keep the host clean
    hf_cache = tmp_path / "hf_cache"
    hf_cache.mkdir()
    os.environ["HF_HOME"] = str(hf_cache)
    
    # We use the smallest Qwen Instruct for the smoke test
    tiny_model = "Qwen/Qwen2.5-0.5B-Instruct"
    
    rag = LocalRAG(db_path=temp_db, model_name=tiny_model)
    
    # Ingest a simple fact
    doc = Document(
        doc_id="fact1", 
        source="internal", 
        title="Testing Fact", 
        content="The official color of the local-rag project is safety orange."
    )
    rag.retriever.ingest([doc])
    
    # Ask a question grounded in that fact
    response = rag.ask("What is the official color of local-rag?", stream=False)
    
    assert "orange" in response.answer.lower()
    assert response.sources[0].doc_id == "fact1"
    
    rag.close()
