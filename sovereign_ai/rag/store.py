import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional

# Try to import SQLCipher, fallback to standard sqlite3
try:
    from sqlcipher3 import dbapi2 as sqlcipher
except ImportError:
    sqlcipher = None

import aiosqlite

logger = logging.getLogger(__name__)

class Store:
    """
    Sovereign Storage Layer using SQLite/SQLCipher.
    
    v0.4.0: Supports full-database encryption via SQLCipher if a password is provided.
    """
    def __init__(self, db_path: str = "sovereign_ai.db", password: Optional[str] = None):
        self.db_path = Path(db_path)
        self.password = password
        self.conn = None
        self._init_db()

    def _init_db(self):
        """Initialize the database, verify FTS5 support, and handle encryption."""
        is_new = not self.db_path.exists()
        
        # 1. Driver Selection & Connection
        if self.password:
            if sqlcipher is None:
                raise ImportError(
                    "sqlcipher3-wheels is required for encrypted databases. "
                    "Install it with: pip install local-rag[secure]"
                )
            self.conn = sqlcipher.connect(str(self.db_path))
            # Must set key immediately. PRAGMA key doesn't support parameterized queries in some drivers.
            escaped_pass = self.password.replace("'", "''")
            self.conn.execute(f"PRAGMA key = '{escaped_pass}'")
        else:
            self.conn = sqlite3.connect(str(self.db_path))
            if is_new:
                # Nudge user toward encryption for fresh sovereign deployments
                logger.warning(
                    "⚠️  Creating unencrypted database. For sovereign deployments, use --password "
                    "or 'local-rag db encrypt' after creation."
                )

        # 2. Verify Access (Unlock Check)
        try:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            # Simple query to verify broad access
            self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1")
        except Exception as e:
            err_msg = str(e).lower()
            if "file is not a database" in err_msg or "encrypted" in err_msg or "authentication" in err_msg:
                raise PermissionError(
                    "[Sovereign Access Denied] Database is encrypted or password invalid."
                ) from e
            raise e
        
        # 3. Verify FTS5 support
        try:
            self.conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS _fts_check USING fts5(c);")
            self.conn.execute("DROP TABLE _fts_check;")
        except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
            raise RuntimeError(
                "FTS5 is not enabled in your local SQLite/SQLCipher build. "
                "local-rag requires FTS5 for lexical indexing."
            ) from e
            
        self._create_tables()

    def _create_tables(self):
        """Create relational and virtual FTS5 tables."""
        # Schema versioning
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY
            )
        """)
        
        # Documents storage
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT -- Generic JSON blob
            )
        """)
        
        # Chunks storage (Relational)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                text TEXT NOT NULL,
                position INTEGER NOT NULL,
                metadata_json TEXT, -- Chunk-specific metadata
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            )
        """)
        
        # FTS5 Virtual Table (Standalone content for search)
        from .config import DEFAULT_FTS_TOKENIZER
        self.conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                text,
                content='chunks',
                tokenize='{DEFAULT_FTS_TOKENIZER}'
            )
        """)
        
        # Bootstrap schema version if new
        cur = self.conn.execute("SELECT COUNT(*) FROM schema_version")
        if cur.fetchone()[0] == 0:
            self.conn.execute("INSERT INTO schema_version (version) VALUES (1)")
            
        self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()

class AsyncStore:
    """
    Asynchronous Sovereign Storage Layer using aiosqlite.
    Provides non-blocking database operations for high-concurrency loops.
    """
    def __init__(self, db_path: str = "sovereign_ai.db", password: Optional[str] = None):
        self.db_path = Path(db_path)
        self.password = password
        self.conn: Optional[aiosqlite.Connection] = None

    async def connect(self):
        """Establish an async connection and handle encryption if needed."""
        # Note: aiosqlite runs sqlite calls in a thread pool.
        self.conn = await aiosqlite.connect(self.db_path)
        
        # Optimization for RAG workloads
        await self.conn.execute("PRAGMA journal_mode=WAL")
        await self.conn.execute("PRAGMA foreign_keys=ON")
        await self.conn.execute("PRAGMA synchronous=NORMAL")
        
        if self.password:
            escaped_pass = self.password.replace("'", "''")
            await self.conn.execute(f"PRAGMA key = '{escaped_pass}'")
            
        await self._create_tables()
        await self.conn.commit()

    async def _create_tables(self):
        """Initialize required relational and virtual tables if they do not exist."""
        from .config import DEFAULT_FTS_TOKENIZER
        
        # 1. Documents table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                doc_id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                title TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata_json TEXT
            )
        """)
        
        # 2. Chunks table
        await self.conn.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                chunk_id TEXT PRIMARY KEY,
                doc_id TEXT NOT NULL,
                text TEXT NOT NULL,
                position INTEGER NOT NULL,
                metadata_json TEXT,
                FOREIGN KEY (doc_id) REFERENCES documents(doc_id) ON DELETE CASCADE
            )
        """)
        
        # 3. FTS5 table
        await self.conn.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
                text,
                content='chunks',
                tokenize='{DEFAULT_FTS_TOKENIZER}'
            )
        """)
        
        # 4. Schema version
        await self.conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER PRIMARY KEY)")
        async with self.conn.execute("SELECT COUNT(*) FROM schema_version") as cursor:
            row = await cursor.fetchone()
            if row[0] == 0:
                await self.conn.execute("INSERT INTO schema_version (version) VALUES (1)")

    async def execute(self, sql: str, parameters: Optional[tuple] = None):
        if not self.conn: await self.connect()
        return await self.conn.execute(sql, parameters or ())

    async def fetchall(self, sql: str, parameters: Optional[tuple] = None):
        if not self.conn: await self.connect()
        async with self.conn.execute(sql, parameters or ()) as cursor:
            return await cursor.fetchall()

    async def commit(self):
        if self.conn:
            await self.conn.commit()

    async def close(self):
        if self.conn:
            await self.conn.close()
