import json
import time
import threading
from typing import Dict, List, Any, Optional

class HotMemoryIndex:
    """
    DuckDB-backed hot memory index for Semantic vector retrieval.
    Enforces deterministic READ constraints against Promotion Pipeline writes.
    """
    def __init__(self, db_path: str = "agent_memory.duckdb", key_manager=None, embedder=None):
        self.db_path = db_path
        self.key_manager = key_manager
        self.embedder = embedder
        self.conn = None
        self.initialized = False
        self._lock = threading.Lock()
        
    def _lazy_init(self, needs_vss: bool = False):
        if self.conn is None:
            import duckdb
            config = {'hnsw_enable_experimental_persistence': 'true'}
            try:
                self.conn = duckdb.connect(self.db_path, config=config)
            except Exception:
                self.conn = duckdb.connect(self.db_path)
                try: self.conn.execute("SET hnsw_enable_experimental_persistence = true;")
                except: pass
                
        if not self.initialized:
            self.conn.execute("CREATE SEQUENCE IF NOT EXISTS events_id_seq START 1")
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY DEFAULT nextval('events_id_seq'),
                    ts DOUBLE,
                    event_type VARCHAR,
                    payload VARCHAR,
                    embedding FLOAT[384]
                )
            """)
            self.initialized = True
            
        if needs_vss:
            try:
                self.conn.execute("INSTALL vss; LOAD vss;")
                self.conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_embedding 
                    ON events USING HNSW (embedding) 
                    WITH (metric = 'cosine')
                """)
            except: pass

    def _decrypt_payload(self, data_str: str) -> str:
        if self.key_manager and self.key_manager.is_encrypted():
            try: return self.key_manager.decrypt(data_str)
            except Exception: return data_str
        return data_str

    def _encrypt_payload(self, data_str: str) -> str:
        if self.key_manager and self.key_manager.is_encrypted():
            return self.key_manager.encrypt(data_str)
        return data_str

    def reader(self):
        """Returns a context manager enforcing SNAPSHOT ISOLATION for read ops."""
        self._lazy_init(needs_vss=True)
        return HotMemoryReader(self.conn, self)

    def write_event(self, event_type: str, payload: Dict[str, Any], text_for_embedding: Optional[str] = None):
        """Standard insertion primarily used by the Promotion Pipeline block."""
        self._lazy_init(needs_vss=True)
        if text_for_embedding is None:
            text_for_embedding = f"{event_type}: {json.dumps(payload)}"

        embedding = None
        if self.embedder:
            try: embedding = self.embedder.encode(text_for_embedding).tolist()
            except: pass

        encrypted_payload = self._encrypt_payload(json.dumps(payload))

        with self._lock:
            # Note: Explicit transactions on writes prevent dirty interactions
            self.conn.execute("BEGIN TRANSACTION")
            if embedding is not None:
                self.conn.execute(
                    "INSERT INTO events (ts, event_type, payload, embedding) VALUES (?, ?, ?, ?)",
                    [time.time(), event_type, encrypted_payload, embedding]
                )
            else:
                self.conn.execute(
                    "INSERT INTO events (ts, event_type, payload) VALUES (?, ?, ?)",
                    (time.time(), event_type, encrypted_payload)
                )
            self.conn.execute("COMMIT")

    def close(self):
        with self._lock:
            if self.conn:
                try: self.conn.close()
                except: pass
                self.conn = None
                self.initialized = False

class HotMemoryReader:
    """Enforces deterministic vector reads without blocking pipeline writes."""
    def __init__(self, conn, index_ref):
        self.conn = conn
        self.index_ref = index_ref

    def __enter__(self):
        # Prevent Phantom Reads mutating top_k returns mid-loop
        self.conn.execute("BEGIN TRANSACTION")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        try: self.conn.execute("COMMIT")
        except: self.conn.execute("ROLLBACK")

    def recall_similar(self, query: str, top_k: int = 5) -> List[Dict]:
        if not self.index_ref.embedder:
            return [{"status": "semantic_search_disabled", "reason": "Embedder not available"}]

        try:
            query_embedding = self.index_ref.embedder.encode(query).tolist()
            results = self.conn.execute("""
                SELECT event_type, payload, array_cosine_similarity(embedding, ?::FLOAT[384]) as score
                FROM events
                ORDER BY score DESC
                LIMIT ?
            """, [query_embedding, top_k]).fetchall()

            return [
                {
                    "event_type": row[0],
                    "payload": json.loads(self.index_ref._decrypt_payload(row[1])),
                    "score": float(row[2])
                }
                for row in results
            ]
        except Exception as e:
            return [{"error": str(e)}]
