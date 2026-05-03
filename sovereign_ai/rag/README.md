# sovereign_ai/rag

> **Canonical home** for all code previously in the `local-rag` satellite repository.

## Purpose

`sovereign_ai.rag` is the **Retrieval-Augmented Generation (RAG) layer** of the Sovereign AI Stack.  It provides:

- Hybrid retrieval: SQLite FTS5 (lexical) + LanceDB (vector) + BGE reranker.
- ABAC policy gateway: role-based access control per principal before retrieval.
- Audit logging: SHA-256-linked append-only JSONL + SQLite event chain.
- An OpenAI-compatible generator backed by a local Ollama/vLLM model.

## Key Classes / Functions

| Symbol | Module | Description |
|---|---|---|
| `RAGPipeline` | `sovereign_ai.rag` | Public alias for `LocalRAG` — the main RAG orchestrator. |
| `LocalRAG` | `sovereign_ai.rag.main` | Synchronous RAG pipeline with governed retrieval. |
| `AsyncLocalRAG` | `sovereign_ai.rag.main` | Async-native RAG pipeline. |
| `embed_documents` | `sovereign_ai.rag` | Embed a list of documents/strings using sentence-transformers. |
| `query` | `sovereign_ai.rag` | Convenience wrapper: `query(pipeline, question)` → `RAGResponse`. |
| `FTS5Retriever` | `sovereign_ai.rag.retriever` | SQLite FTS5 lexical retriever. |
| `QwenGenerator` | `sovereign_ai.rag.generator` | Local LLM generator (Ollama/Qwen). |

## Quick Start

```python
from sovereign_ai.rag import RAGPipeline, query

pipeline = RAGPipeline(db_path="sovereign.db")
response = query(pipeline, "What is Sovereign AI?")
print(response.answer)
```

### Embedding

```python
from sovereign_ai.rag import embed_documents

vectors = embed_documents(["Hello world", "Sovereign AI is local-first."])
print(vectors.shape)  # (2, 384)
```

## Migration Note

This module is the **canonical home** for all code previously in the `local-rag` satellite repository.  If you were importing from `local_rag`, update your imports to use `sovereign_ai.rag` instead.

See [docs/MIGRATION.md](../../docs/MIGRATION.md) for full migration instructions.
