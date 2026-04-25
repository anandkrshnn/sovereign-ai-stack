import os
import json
import asyncio
import logging
import uuid
from typing import List, Dict, Optional, Any
import numpy as np

try:
    import asyncpg
    from pgvector.asyncpg import register_vector
except ImportError:
    asyncpg = None

try:
    import lancedb
except ImportError:
    lancedb = None

from sentence_transformers import SentenceTransformer
from .schemas import Chunk, SearchResult

logger = logging.getLogger(__name__)

class LanceVectorStore:
    """
    Local-first Sovereign Vector Storage using LanceDB.
    Provides semantic search capabilities without external dependencies (Postgres).
    """
    def __init__(
        self, 
        uri: str = ".cache/lancedb", 
        table_name: str = "chunks",
        model_name: str = "BAAI/bge-small-en-v1.5"
    ):
        if lancedb is None:
            raise ImportError("lancedb is required for LanceVectorStore. Install with 'pip install lancedb'")
        
        self.uri = uri
        self.table_name = table_name
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        
        # Ensure path exists
        os.makedirs(os.path.dirname(os.path.abspath(uri)) if "/" in uri else ".", exist_ok=True)
        self.db = lancedb.connect(uri)
        self._table = None

    def _get_table(self):
        if self._table is None:
            if self.table_name in self.db.table_names():
                self._table = self.db.open_table(self.table_name)
        return self._table

    async def embed(self, texts: List[str]) -> List[np.ndarray]:
        """Generate semantic embeddings (offloaded to thread)."""
        return await asyncio.to_thread(self.model.encode, texts)

    async def ingest_batch(self, chunks: List[Chunk], tenant_id: Optional[str] = None):
        """Embed and store chunks in the local LanceDB table."""
        texts = [c.text for c in chunks]
        embeddings = await self.embed(texts)
        
        data = []
        for chunk, emb in zip(chunks, embeddings):
            record = {
                "vector": emb,
                "text": chunk.text,
                "doc_id": chunk.doc_id,
                "chunk_id": chunk.chunk_id,
                "tenant_id": tenant_id or chunk.metadata.get("tenant_id", "default"),
                "metadata": chunk.metadata
            }
            data.append(record)
            
        if self._table is None and self.table_name not in self.db.table_names():
            # Create table if it doesn't exist
            self._table = self.db.create_table(self.table_name, data=data, mode="append")
        else:
            table = self._get_table()
            if table: table.add(data)
            else: self._table = self.db.create_table(self.table_name, data=data)

    async def search(self, query: str, top_k: int = 5, tenant_id: Optional[str] = None) -> List[SearchResult]:
        """Local semantic search."""
        table = self._get_table()
        if table is None: return []
        
        query_emb = (await self.embed([query]))[0]
        
        # Build query
        query_builder = table.search(query_emb).limit(top_k)
        
        # Add tenant isolation filter
        if tenant_id:
            query_builder = query_builder.where(f"tenant_id = '{tenant_id}'")
            
        df = query_builder.to_pandas()
        
        results = []
        for _, row in df.iterrows():
            # LanceDB distance is L2 by default; convert to score (approximate)
            score = 1.0 / (1.0 + row.get("_distance", 0))
            
            results.append(SearchResult(
                doc_id=row["doc_id"],
                chunk_id=row["chunk_id"],
                text=row["text"],
                score=float(score),
                metadata=row["metadata"]
            ))
        return results

    async def close(self):
        pass

class PgVectorStore:
    """
    Production-grade Vector Storage using Postgres + pgvector.
    Evolves local-rag from lexical-only to true Hybrid Retrieval.
    """
    def __init__(
        self, 
        dsn: Optional[str] = None, 
        model_name: str = "BAAI/bge-small-en-v1.5",
        dimension: int = 384
    ):
        self.dsn = dsn or os.getenv("PGVECTOR_URL")
        self.model_name = model_name
        self.dimension = dimension
        self.model = SentenceTransformer(model_name)
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        if not self.dsn:
            raise ValueError("PGVECTOR_URL environment variable or DSN must be provided.")
        
        if asyncpg is None:
            raise ImportError("asyncpg and pgvector are required for PgVectorStore.")

        self.pool = await asyncpg.create_pool(self.dsn)
        
        async with self.pool.acquire() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            await register_vector(conn)
            
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS chunks_vector (
                    id uuid PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    chunk_id TEXT NOT NULL,
                    text TEXT NOT NULL,
                    embedding vector({self.dimension}),
                    metadata jsonb
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS chunks_vector_hnsw_idx 
                ON chunks_vector USING hnsw (embedding vector_cosine_ops)
            """)

    async def embed(self, texts: List[str]) -> List[np.ndarray]:
        return await asyncio.to_thread(self.model.encode, texts)

    async def ingest_batch(self, chunks: List[Chunk], tenant_id: Optional[str] = None):
        if not self.pool: await self.connect()
        
        texts = [c.text for c in chunks]
        embeddings = await self.embed(texts)
        
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                for chunk, emb in zip(chunks, embeddings):
                    meta = chunk.metadata.copy()
                    if tenant_id: meta["tenant_id"] = tenant_id
                    
                    await conn.execute("""
                        INSERT INTO chunks_vector (id, doc_id, chunk_id, text, embedding, metadata)
                        VALUES ($1, $2, $3, $4, $5, $6)
                    """, 
                    uuid.uuid4(),
                    chunk.doc_id, 
                    chunk.chunk_id, 
                    chunk.text, 
                    emb, 
                    json.dumps(meta))

    async def search(self, query: str, top_k: int = 5, tenant_id: Optional[str] = None) -> List[SearchResult]:
        if not self.pool: await self.connect()
        query_emb = (await self.embed([query]))[0]
        
        async with self.pool.acquire() as conn:
            await register_vector(conn)
            if tenant_id:
                sql = """
                    SELECT doc_id, chunk_id, text, (1 - (embedding <=> $1)) as score, metadata
                    FROM chunks_vector
                    WHERE metadata->>'tenant_id' = $2
                    ORDER BY embedding <=> $1
                    LIMIT $3
                """
                rows = await conn.fetch(sql, query_emb, tenant_id, top_k)
            else:
                sql = """
                    SELECT doc_id, chunk_id, text, (1 - (embedding <=> $1)) as score, metadata
                    FROM chunks_vector
                    ORDER BY embedding <=> $1
                    LIMIT $2
                """
                rows = await conn.fetch(sql, query_emb, top_k)
                
            results = []
            for r in rows:
                results.append(SearchResult(
                    doc_id=r["doc_id"],
                    chunk_id=r["chunk_id"],
                    text=r["text"],
                    score=float(r["score"]),
                    metadata=json.loads(r["metadata"]) if isinstance(r["metadata"], str) else r["metadata"]
                ))
            return results

    async def close(self):
        if self.pool:
            await self.pool.close()
