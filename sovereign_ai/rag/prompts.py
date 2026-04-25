from .config import DEFAULT_SYSTEM_PROMPT

RAG_USER_PROMPT = """Use the following context snippets to answer the query. If you cannot answer using the context, state that clearly.

---
CONTEXT:
{context}
---

QUERY: {query}
"""

def format_context(results) -> str:
    """Format a list of SearchResult objects into a coherent context block."""
    context_blocks = []
    for i, r in enumerate(results, 1):
        # We strip the [result] tags from retriever previews if they exist
        clean_text = r.text.replace("[result]", "").replace("[/result]", "")
        context_blocks.append(f"[{i}] source: {r.doc_id}\n{clean_text}")
    
    return "\n\n".join(context_blocks)
