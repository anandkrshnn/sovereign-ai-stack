import os
import lancedb
import duckdb
import time
import hashlib
from typing import Optional, Dict, Any, Tuple
from sentence_transformers import SentenceTransformer
import torch

class SovereignSemanticCache:
    """
    Sovereign Semantic Cache using BGE-Small-EN-v1.5 + LanceDB + DuckDB.
    
    Ensures that semantically similar queries are resolved locally in sub-ms time
    without redundant calls to the LLM backend.
    """
    
    def __init__(
        self, 
        base_dir: str = "data",
        tenant_id: str = "default",
        model_name: str = "BAAI/bge-small-en-v1.5",
        threshold: float = 0.92,
        ttl_hours: int = 24
    ):
        # Physical Isolation: /{base_dir}/{tenant_id}/cache/
        self.tenant_id = tenant_id
        self.cache_dir = os.path.join(base_dir, tenant_id, "cache")
        self.threshold = threshold
        self.ttl_hours = ttl_hours
        
        # 1. Initialize Embedding Model
        device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = SentenceTransformer(model_name, device=device)
        
        # 2. Initialize LanceDB (Vector Store)
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir, exist_ok=True)
        
        self.db = lancedb.connect(self.cache_dir)
        self._ensure_table()
        
        # 3. Initialize DuckDB (Metadata Store)
        self.con = duckdb.connect(os.path.join(self.cache_dir, "metadata.db"))
        self._ensure_metadata_schema()

    def _ensure_table(self):
        if "semantic_cache" not in self.db.list_tables():
            # Initial schema for the vector table
            self.db.create_table("semantic_cache", [
                {"vector": [0.0] * 384, "prompt_hash": "init", "timestamp": 0.0}
            ])

    def _ensure_metadata_schema(self):
        self.con.execute("""
            CREATE TABLE IF NOT EXISTS cache_metadata (
                prompt_hash VARCHAR PRIMARY KEY,
                original_prompt TEXT,
                response_text TEXT,
                model VARCHAR,
                principal VARCHAR,
                created_at DOUBLE
            )
        """)

    def lookup(self, prompt: str, principal: str) -> Optional[Tuple[str, str]]:
        """
        Perform a semantic lookup with TTL enforcement (v0.4.0).
        """
        # 1. Compute Embedding
        query_vec = self.model.encode(prompt, normalize_embeddings=True)
        
        # 2. Search LanceDB
        table = self.db.open_table("semantic_cache")
        results = table.search(query_vec.tolist()).limit(1).to_list()
        
        if not results:
            return None
        
        l2_dist_sq = results[0].get("_distance", 1.0)
        similarity = 1 - (l2_dist_sq / 2)
        ts = results[0].get("timestamp", 0.0)
        
        # TTL Check
        if time.time() - ts > (self.ttl_hours * 3600):
            return None # Expired
            
        if similarity >= self.threshold:
            prompt_hash = results[0]["prompt_hash"]
            
            # 3. Retrieve from DuckDB
            meta = self.con.execute(
                "SELECT response_text, model FROM cache_metadata WHERE prompt_hash = ? AND principal = ?", 
                [prompt_hash, principal]
            ).fetchone()
            
            if meta:
                return meta
        
        return None

    def store(self, prompt: str, response: str, model: str, principal: str):
        """Store a new prompt-response pair in the cache with timestamp."""
        import hashlib
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        query_vec = self.model.encode(prompt, normalize_embeddings=True)
        ts = time.time()
        
        # 1. Store Vector
        table = self.db.open_table("semantic_cache")
        table.add([{
            "vector": query_vec.tolist(),
            "prompt_hash": prompt_hash,
            "timestamp": ts
        }])
        
        # 2. Store Metadata
        self.con.execute(
            "INSERT OR REPLACE INTO cache_metadata VALUES (?, ?, ?, ?, ?, ?)",
            [prompt_hash, prompt, response, model, principal, ts]
        )

    def evict_expired(self):
        """Cleanup logic for v0.4.0 cache hygiene."""
        cutoff = time.time() - (self.ttl_hours * 3600)
        
        # 1. DuckDB Cleanup
        self.con.execute("DELETE FROM cache_metadata WHERE created_at < ?", [cutoff])
        
        # 2. LanceDB Cleanup
        table = self.db.open_table("semantic_cache")
        table.delete(f"timestamp < {cutoff}")
        
    def close(self):
        self.con.close()
