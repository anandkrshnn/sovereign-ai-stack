from typing import Dict, Any, List
from localagent.memory.lancedb_store import LanceDBStore
from localagent.memory.promotion_pipeline import MemoryPromotionPipeline
from localagent.broker.engine import LocalPermissionBroker

class MemoryService:
    def __init__(self, broker: LocalPermissionBroker, lancedb_path: str, duckdb_path: str, key_manager=None):
        self.lancedb_store = LanceDBStore(db_path=lancedb_path, key_manager=key_manager)
        self.promotion_pipeline = MemoryPromotionPipeline(self.lancedb_store)
        self.broker = broker
        self.key_manager = key_manager
        from localagent.memory.duckdb_index import HotMemoryIndex
        from localagent.memory import get_embedder # Keep lazy initializer
        self.hot_memory = HotMemoryIndex(db_path=duckdb_path, key_manager=key_manager, embedder=get_embedder())

    def get_governed_context(self, user_query: str, session_context: Dict[str, Any]):
        """Governed retrieval: LPB check + Sensitivity filtering + LanceDB Search."""

        # 1. LPB retrieval-time authorization check
        perm = self.broker.request_permission(
            intent="read_memory",
            resource="semantic_memory",
            context=session_context
        )

        if not perm.get("granted", False):
            return {"memories": [], "reason": "access_denied_by_lpb"}

        # 2. Semantic retrieval from memory_items (LanceDB)
        # In a real system, we'd use vector search. For now, we fetch and filter.
        all_items = self.lancedb_store.get_memory_items()
        
        authorized_memories = []
        for item in all_items:
            # Governance Logic:
            # - High: Only if status == "approved"
            # - Medium/Low: Always if authorized by LPB
            if item.get("sensitivity") == "High" and item.get("status") != "approved":
                continue
                
            authorized_memories.append({
                "body": item["body"],
                "sensitivity": item["sensitivity"],
                "kind": item.get("memory_type"),
                "confidence": item["confidence"]
            })

        # 3. Fallback/Supplement with Hot Memory (DuckDB) for recent tool results
        with self.hot_memory.reader() as reader:
            hot_results = reader.recall_similar(user_query, top_k=3)
        
        for h in hot_results:
            if "error" in h or "status" in h: continue
            
            body = h.get("text") or ""
            if not body:
                payload = h.get("payload", {})
                body = payload.get("content") or payload.get("text") or str(payload)
                
            authorized_memories.append({
                "body": body,
                "sensitivity": "Low", # Default hot memory to Low sensitivity
                "kind": "recent_history",
                "confidence": h.get("score", 0.5)
            })

        return {
            "memories": authorized_memories[:7], # Limit context size
            "reason": "authorized",
            "retrieval_count": len(authorized_memories)
        }

    def refresh_hot_cache(self):
        """Rebuild DuckDB hot memory from approved LanceDB items."""
        if not hasattr(self, 'hot_memory'): return
        
        # 1. Get approved items from LanceDB
        approved_items = self.lancedb_store.get_memory_items(status="approved")
        
        # 2. Rebuild index pipeline bounds
        for item in approved_items:
            self.hot_memory.write_event(
                event_type="canonical_memory",
                payload={"body": item["body"], "kind": item.get("memory_type")},
                text_for_embedding=item["body"]
            )
        print(f"[MemoryService] Hot cache refreshed with {len(approved_items)} items.")

    def get_stats(self) -> Dict[str, Any]:
        """Aggregate stats from all memory engines."""
        lancedb_count = 0
        hot_memory_count = 0
        status = "healthy"
        
        # 1. LanceDB counts
        try:
            if self.lancedb_store:
                self.lancedb_store._lazy_init()
                if self.lancedb_store.memory_items:
                    lancedb_count = self.lancedb_store.memory_items.count_rows()
        except Exception as e:
            status = f"lancedb_degraded: {str(e)}"
            
        # 2. Hot Memory counts
        try:
            if self.hot_memory:
                with self.hot_memory.reader() as reader:
                    # Check if table exists first (defensive)
                    tables = reader.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='memory_items'").fetchall()
                    if tables:
                        res = reader.conn.execute("SELECT COUNT(*) FROM memory_items").fetchone()
                        hot_memory_count = res[0] if res else 0
        except Exception as e:
            status = f"hot_memory_degraded: {str(e)}"

        return {
            "lancedb_items": lancedb_count,
            "hot_memory_items": hot_memory_count,
            "total": lancedb_count + hot_memory_count,
            "status": status
        }

    def close(self):
        """Shutdown all memory engines."""
        if hasattr(self, 'hot_memory') and self.hot_memory:
            self.hot_memory.close()
        if hasattr(self, 'lancedb_store') and self.lancedb_store:
            self.lancedb_store.close()
