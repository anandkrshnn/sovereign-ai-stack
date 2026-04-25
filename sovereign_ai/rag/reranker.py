from typing import List, Optional
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch
import logging

from .schemas import SearchResult

logger = logging.getLogger(__name__)

class BGEReranker:
    """
    Cross-encoder reranker using BAAI/bge-reranker-base.
    
    Usage: Applied AFTER policy filtering in GovernedRetriever to improve precision.
    The cross-encoder evaluates the query and document pair simultaneously for superior 
    semantic relevance scoring compared to bi-encoders or lexical search.
    """
    
    def __init__(self, model_name: str = "BAAI/bge-reranker-base", device: Optional[str] = None):
        """
        Initialize the reranker model and tokenizer.
        
        Args:
            model_name: HuggingFace model ID for the cross-encoder.
            device: 'cuda', 'cpu', or 'mps'. Auto-detected if None.
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        
        logger.info(f"Initializing Reranker: {model_name} on {self.device}")
        
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
        except Exception as e:
            logger.error(f"Failed to load reranker model: {e}")
            raise RuntimeError(f"Reranker initialization failed: {e}")
    
    def rerank(self, query: str, results: List[SearchResult], top_k: int = 5) -> List[SearchResult]:
        """
        Rerank policy-approved chunks using cross-encoder scoring.
        
        Args:
            query: User query string.
            results: List of SearchResult objects (usually from FTS5 + Policy filter).
            top_k: Number of top reranked results to return.
        
        Returns:
            Reranked list of SearchResults with updated scores, sorted by relevance.
        """
        if not results:
            return []
        
        # Prepare pairs for cross-encoder processing
        pairs = [[query, res.text] for res in results]
        
        logger.debug(f"Reranking {len(results)} chunks for query: '{query[:50]}...'")
        
        with torch.no_grad():
            inputs = self.tokenizer(
                pairs,
                padding=True,
                truncation=True,
                return_tensors="pt",
                max_length=512
            ).to(self.device)
            
            # Cross-encoders typically output a single logit representing the relevance score
            logits = self.model(**inputs).logits
            
            # Convert to list of scores
            scores = logits.view(-1).cpu().tolist()
        
        # Update scores in SearchResult objects
        # Note: BGE Reranker scores are not necessarily [0, 1]
        for res, score in zip(results, scores):
            res.score = float(score)
        
        # Sort by updated scores in descending order
        reranked = sorted(results, key=lambda x: x.score, reverse=True)
        
        # Log the top result's score for observability
        if reranked:
            logger.debug(f"Top reranked score: {reranked[0].score:.4f}")
            
        return reranked[:top_k]
