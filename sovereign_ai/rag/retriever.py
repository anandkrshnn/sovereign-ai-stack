import json
import uuid
from typing import List, Dict, Optional
from datetime import datetime

from .store import Store, AsyncStore
from .schemas import Document, Chunk, SearchResult
from .utils import chunk_text
from .config import DEFAULT_DB_PATH, DEFAULT_SNIPPET_TOKENS

class FTS5Retriever:
    def __init__(self, db_path: str = DEFAULT_DB_PATH, password: Optional[str] = None):
        self.store = Store(db_path, password=password)

    def ingest(self, docs: List[Document], chunk_size: int = 1000, chunk_overlap: int = 200):
        """Split documents into chunks and ingest into relational and FTS5 tables."""
        conn = self.store.conn
        try:
            for doc in docs:
                # Merge governance fields into metadata for persistence
                meta = doc.metadata.copy()
                if doc.classification: meta["classification"] = doc.classification
                if doc.department: meta["department"] = doc.department
                if doc.tenant_id: meta["tenant_id"] = doc.tenant_id
                if doc.owner: meta["owner"] = doc.owner

                conn.execute("""
                    INSERT OR REPLACE INTO documents (doc_id, source, title, created_at, updated_at, metadata_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    doc.doc_id, 
                    doc.source, 
                    doc.title, 
                    doc.created_at.isoformat(), 
                    doc.updated_at.isoformat(), 
                    json.dumps(meta)
                ))

                # 2. Split into Chunks
                text_chunks = chunk_text(doc.content, chunk_size, chunk_overlap)
                
                for i, text in enumerate(text_chunks):
                    chunk_id = str(uuid.uuid4())
                    
                    # 3. Insert into relational chunks table
                    cur = conn.execute("""
                        INSERT INTO chunks (chunk_id, doc_id, text, position, metadata_json)
                        VALUES (?, ?, ?, ?, ?) RETURNING rowid
                    """, (chunk_id, doc.doc_id, text, i, json.dumps({})))
                    rowid = cur.fetchone()[0]
                    
                    # 4. Insert into FTS5 table
                    conn.execute("INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)", (rowid, text))

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e

    def search(self, query: str, top_k: int = 5, snippet_tokens: int = DEFAULT_SNIPPET_TOKENS) -> List[SearchResult]:
        """Search using FTS5 MATCH and BM25 ranking."""
        # Sanitize query: FTS5 MATCH is sensitive to special characters like '?', '*', ':', etc.
        # We strip characters that have special meaning in FTS5 to prevent OperationalError.
        sanitized_query = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
        
        # Use OR between words to improve recall for natural language questions
        keywords = sanitized_query.split()
        if not keywords:
            return []
        fts_query = " OR ".join(keywords)
        
        # Use snippet() to get a contextual preview
        # bm25() returns a score (lower is better in SQLite, so we negate it for consistency)
        sql = f"""
            SELECT 
                c.doc_id, 
                c.chunk_id, 
                snippet(chunks_fts, 0, '[result]', '[/result]', '...', {snippet_tokens}) as preview,
                bm25(chunks_fts) as score,
                d.metadata_json
            FROM chunks_fts f
            JOIN chunks c ON f.rowid = c.rowid
            JOIN documents d ON c.doc_id = d.doc_id
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """
        
        cur = self.store.conn.execute(sql, (fts_query, top_k))
        results = []
        for r in cur.fetchall():
            results.append(SearchResult(
                doc_id=r[0],
                chunk_id=r[1],
                text=r[2], # Using the snippet as text for preview
                score=-r[3], # Negate BM25 (lower is better) to show higher is better
                metadata=json.loads(r[4]) if r[4] else {}
            ))
        return results

    def close(self):
        self.store.close()

class AsyncFTS5Retriever:
    """
    Asynchronous FTS5 Retriever.
    Evolves the lexical engine to support non-blocking search and high-throughput batch ingestion.
    """
    def __init__(self, db_path: str = DEFAULT_DB_PATH, password: Optional[str] = None):
        self.store = AsyncStore(db_path, password=password)

    async def ingest_batch(self, docs: List[Document], chunk_size: int = 1000, chunk_overlap: int = 200):
        """Asynchronously ingest documents in batches to avoid blocking the event loop."""
        # Using the same logic as sync ingest but with await
        for doc in docs:
            meta = doc.metadata.copy()
            if doc.classification: meta["classification"] = doc.classification
            if doc.department: meta["department"] = doc.department
            if doc.tenant_id: meta["tenant_id"] = doc.tenant_id
            if doc.owner: meta["owner"] = doc.owner

            await self.store.execute("""
                INSERT OR REPLACE INTO documents (doc_id, source, title, created_at, updated_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                doc.doc_id, doc.source, doc.title, 
                doc.created_at.isoformat(), doc.updated_at.isoformat(), 
                json.dumps(meta)
            ))

            text_chunks = chunk_text(doc.content, chunk_size, chunk_overlap)
            
            for i, text in enumerate(text_chunks):
                chunk_id = str(uuid.uuid4())
                
                # Relational insert
                cursor = await self.store.execute("""
                    INSERT INTO chunks (chunk_id, doc_id, text, position, metadata_json)
                    VALUES (?, ?, ?, ?, ?) RETURNING rowid
                """, (chunk_id, doc.doc_id, text, i, json.dumps({})))
                
                row = await cursor.fetchone()
                rowid = row[0]
                
                # FTS5 insert
                await self.store.execute("INSERT INTO chunks_fts (rowid, text) VALUES (?, ?)", (rowid, text))

        await self.store.commit()

    async def search(self, query: str, top_k: int = 5, snippet_tokens: int = DEFAULT_SNIPPET_TOKENS) -> List[SearchResult]:
        """Asynchronous lexical search using FTS5."""
        sanitized_query = "".join(c if c.isalnum() or c.isspace() else " " for c in query).strip()
        keywords = sanitized_query.split()
        if not keywords: return []
        fts_query = " OR ".join(keywords)
        
        sql = f"""
            SELECT c.doc_id, c.chunk_id, 
                   snippet(chunks_fts, 0, '[result]', '[/result]', '...', {snippet_tokens}) as preview,
                   bm25(chunks_fts) as score,
                   d.metadata_json
            FROM chunks_fts f
            JOIN chunks c ON f.rowid = c.rowid
            JOIN documents d ON c.doc_id = d.doc_id
            WHERE chunks_fts MATCH ?
            ORDER BY score
            LIMIT ?
        """
        
        rows = await self.store.fetchall(sql, (fts_query, top_k))
        
        results = []
        for r in rows:
            results.append(SearchResult(
                doc_id=r[0], chunk_id=r[1], text=r[2],
                score=-r[3], metadata=json.loads(r[4]) if r[4] else {}
            ))
        return results

    async def close(self):
        await self.store.close()
