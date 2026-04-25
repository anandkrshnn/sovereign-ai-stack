import os
import time
import asyncio
import logging
from typing import Optional, List, Dict
import lancedb
import pyarrow as pa
from sentence_transformers import SentenceTransformer

from .schemas import RAGResponse, SearchResult

logger = logging.getLogger(__name__)

class SemanticCache:
    """
    Sub-millisecond Semantic Cache for rephrased RAG queries.
    Utilizes LanceDB for high-performance localized vector hits.
    """
    def __init__(
        self, 
        cache_dir: str = ".cache",
        model_name: str = "BAAI/bge-small-en-v1.5",
        distance_threshold: float = 0.2 # Cosine distance (lower is closer)
    ):
        self.cache_dir = cache_dir
        self.model_name = model_name
        self.threshold = distance_threshold
        self.model = SentenceTransformer(model_name)
        
        # Initialize LanceDB
        os.makedirs(cache_dir, exist_ok=True)
        self.db = lancedb.connect(cache_dir)
        self._ensure_table()

    def _ensure_table(self):
        """Standard cache schema: query_vector + response data."""
        # Initial schema
        schema = pa.schema([
            pa.field("vector", pa.list_(pa.float32(), 384)),
            pa.field("query", pa.string()),
            pa.field("answer", pa.string()),
            pa.field("sources_json", pa.string()),
            pa.field("tenant_id", pa.string()),
            pa.field("timestamp", pa.float64())
        ])
        try:
            self.db.create_table("semantic_cache", schema=schema)
        except (ValueError, Exception):
            # Already exists or other initialization issue
            pass

    async def get(self, query: str, tenant_id: Optional[str] = None) -> Optional[RAGResponse]:
        """Lookup query in semantic cache."""
        # Embed query (offload to thread)
        emb = await asyncio.to_thread(self.model.encode, query)
        
        table = self.db.open_table("semantic_cache")
        
        # Search using LanceDB optimized vector search
        # We manually filter by tenant_id if provided
        query_proc = table.search(emb).limit(1)
        if tenant_id:
            query_proc = query_proc.where(f"tenant_id = '{tenant_id}'")
            
        results = query_proc.to_pandas()
        
        if len(results) > 0:
            best_match = results.iloc[0]
            # LanceDB distance is squared Euclidean or Cosine depending on ops
            # Default for LanceDB is often L2, but we can check distance
            # Here we just look at the score
            if "_distance" in best_match and best_match["_distance"] < self.threshold:
                logger.info(f"🚀 Semantic Cache Hit (dist={best_match['_distance']:.4f})")
                sources = [SearchResult(**s) for s in json.loads(best_match["sources_json"])]
                return RAGResponse(
                    answer=best_match["answer"],
                    sources=sources,
                    model_name=f"cached({self.model_name})"
                )
        return None

    async def set(self, query: str, response: RAGResponse, tenant_id: Optional[str] = None):
        """Store query and response in semantic cache."""
        emb = await asyncio.to_thread(self.model.encode, query)
        
        table = self.db.open_table("semantic_cache")
        
        data = [{
            "vector": emb.tolist(),
            "query": query,
            "answer": response.answer,
            "sources_json": json.dumps([s.model_dump() for s in response.sources]),
            "tenant_id": tenant_id or "default",
            "timestamp": time.time()
        }]
        
        table.add(data)

import json
