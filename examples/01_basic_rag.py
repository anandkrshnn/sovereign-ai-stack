import os
from sovereign_ai import LocalRAG, Document

def run_basic_rag():
    # 1. Initialize LocalRAG with an in-memory database for the demo
    # In practice, use a persistent path like 'data/my_docs.db'
    rag = LocalRAG(db_path=":memory:")
    
    # 2. Ingest some documents
    print("Ingesting sample documents...")
    docs = [
        Document(
            doc_id="doc_001",
            content="The Sovereign AI Stack (v1.1.0) provides a Verified Airlock for local LLMs.",
            metadata={"source": "manual"}
        ),
        Document(
            doc_id="doc_002",
            content="Deterministic verification is achieved via NLI cross-encoders like DeBERTa-v3.",
            metadata={"source": "manual"}
        )
    ]
    rag.retriever.ingest(docs)
    
    # 3. Ask a question
    query = "How is deterministic verification achieved in the stack?"
    print(f"\nQuery: {query}")
    
    result = rag.ask(query)
    
    # 4. Show results
    print(f"\nAnswer: {result.answer}")
    print("\nSources used:")
    for i, src in enumerate(result.sources, 1):
        print(f"  [{i}] {src.doc_id}: {src.text[:50]}...")

if __name__ == "__main__":
    run_basic_rag()
