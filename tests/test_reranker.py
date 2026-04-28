import pytest
from unittest.mock import patch, MagicMock
from sovereign_ai.rag.reranker import BGEReranker
from sovereign_ai.rag.schemas import SearchResult

@pytest.fixture
def mock_results():
    return [
        SearchResult(doc_id="d1", chunk_id="c1", text="The capital of France is Paris.", score=0.5, metadata={"tenant_id": "default"}),
        SearchResult(doc_id="d2", chunk_id="c2", text="France has a population of 67 million.", score=0.4, metadata={"tenant_id": "default"}),
        SearchResult(doc_id="d3", chunk_id="c3", text="Berlin is the capital of Germany.", score=0.3, metadata={"tenant_id": "default"})
    ]

def test_reranker_sorting(mock_results):
    """Test that the reranker sorts results based on cross-encoder scores."""
    with patch("transformers.AutoTokenizer.from_pretrained"), \
         patch("transformers.AutoModelForSequenceClassification.from_pretrained") as mock_model:
        
        mock_instance = mock_model.return_value
        mock_instance.return_dict = True
        
        mock_logits = MagicMock()
        mock_logits.view.return_value.cpu.return_value.tolist.return_value = [10.0, 5.0, 1.0]
        mock_instance.return_value.logits = mock_logits
        
        reranker = BGEReranker(model_name="mock-model", device="cpu")
        reranked = reranker.rerank("What is the capital of France?", mock_results, top_k=2)
        
        assert len(reranked) == 2
        assert reranked[0].doc_id == "d1"
        assert reranked[0].score == 10.0

def test_reranker_integration_in_governed(mock_results):
    """Test that GovernedRetriever utilizes the reranker correctly."""
    from sovereign_ai.rag.governed import GovernedRetriever
    from sovereign_ai.rag.schemas import PolicyDecision
    
    with patch("sovereign_ai.rag.governed.FTS5Retriever"), \
         patch("sovereign_ai.rag.governed.PolicyEngine") as mock_engine_cls, \
         patch("sovereign_ai.rag.governed.SovereignAuditLogger"), \
         patch("sovereign_ai.rag.governed.BGEReranker") as mock_reranker_class:
        
        mock_reranker = mock_reranker_class.return_value
        mock_reranker.rerank.return_value = [mock_results[0]]
        
        mock_engine = mock_engine_cls.return_value
        mock_engine.evaluate_request.return_value = PolicyDecision(
            action="allow", 
            reason="test", 
            allowed_chunks=["c1", "c2", "c3"]
        )
        
        # Setup retriever
        gr = GovernedRetriever(db_path="mock.db", policy_path="mock.yaml", use_reranker=True)
        gr.retriever.search.return_value = mock_results
        
        results, decision = gr.search("query", top_k=10, rerank_top_k=1)
        
        assert len(results) == 1
        assert results[0].doc_id == "d1"
        mock_reranker.rerank.assert_called_once()
