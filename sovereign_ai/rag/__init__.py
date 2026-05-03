"""
sovereign_ai.rag — canonical home for all code previously in the ``local-rag`` satellite repo.
"""

from .retriever import FTS5Retriever
from .generator import QwenGenerator
from .main import LocalRAG, AsyncLocalRAG

# RAGPipeline is the public alias for LocalRAG
RAGPipeline = LocalRAG


def embed_documents(documents, model_name: str = "BAAI/bge-small-en-v1.5"):
    """Embed a list of documents and return their vector representations.

    This is a convenience wrapper around the sentence-transformers library.
    ``documents`` can be a list of strings or
    :class:`sovereign_ai.rag.schemas.Document` objects (the ``.content``
    attribute is used in that case).

    Args:
        documents: List of strings or Document objects to embed.
        model_name: HuggingFace model identifier for the embedding model.

    Returns:
        A numpy array of shape ``(len(documents), embedding_dim)``.
    """
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:  # pragma: no cover
        raise ImportError(
            "sentence-transformers is required for embed_documents. "
            "Install it with: pip install sentence-transformers"
        ) from exc

    texts = [
        doc.content if hasattr(doc, "content") else str(doc) for doc in documents
    ]
    model = SentenceTransformer(model_name)
    return model.encode(texts)


def query(rag_pipeline: RAGPipeline, question: str, **kwargs):
    """Run a query against a :class:`RAGPipeline` instance.

    A thin convenience wrapper so callers can do::

        from sovereign_ai.rag import query, RAGPipeline
        pipe = RAGPipeline()
        result = query(pipe, "What is sovereign AI?")

    Args:
        rag_pipeline: An initialised :class:`RAGPipeline` instance.
        question: The natural-language question to ask.
        **kwargs: Additional keyword arguments forwarded to
                  :meth:`RAGPipeline.ask`.

    Returns:
        A :class:`sovereign_ai.rag.schemas.RAGResponse` object.
    """
    return rag_pipeline.ask(question, **kwargs)


__all__ = [
    "FTS5Retriever",
    "QwenGenerator",
    "LocalRAG",
    "AsyncLocalRAG",
    "RAGPipeline",
    "embed_documents",
    "query",
]
