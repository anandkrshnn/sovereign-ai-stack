import sqlite3
import json
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone, timedelta

class PersistentIdempotencyStore:
    """
    SQLite-backed idempotency store to ensure safety across restarts.
    Used for HIGH and HALT risk actions in the Sovereign AI Stack.
    """
    def __init__(self, db_path: str, ttl_seconds: int = 3600):
        self.db_path = Path(db_path)
        self.ttl_seconds = ttl_seconds
        self._init_db()

    def _init_db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS idempotency (
                    idem_key TEXT PRIMARY KEY,
                    status TEXT,
                    created_at TIMESTAMP,
                    expires_at TIMESTAMP
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_expires ON idempotency(expires_at)")

    def get_status(self, idem_key: str) -> Optional[str]:
        self._cleanup()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT status FROM idempotency WHERE idem_key = ? AND expires_at > ?", 
                (idem_key, datetime.now(timezone.utc).isoformat())
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def set_status(self, idem_key: str, status: str):
        now = datetime.now(timezone.utc)
        expires = now + timedelta(seconds=self.ttl_seconds)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO idempotency (idem_key, status, created_at, expires_at)
                VALUES (?, ?, ?, ?)
            """, (idem_key, status, now.isoformat(), expires.isoformat()))

    def _cleanup(self):
        """Remove expired entries."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM idempotency WHERE expires_at < ?", (datetime.now(timezone.utc).isoformat(),))
