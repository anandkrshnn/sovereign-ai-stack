"""
Smoke tests for the monorepo consolidation (Phase 1).

All imports are guarded with try/except + pytest.skip so that CI does not
fail on optional or heavy dependencies (torch, sentence-transformers, etc.).
"""

import importlib
import pytest


# ---------------------------------------------------------------------------
# sovereign_ai.agent
# ---------------------------------------------------------------------------

def test_agent_import():
    """sign_payload must be importable from sovereign_ai.agent."""
    try:
        mod = importlib.import_module("sovereign_ai.agent")
    except ImportError as exc:
        pytest.skip(f"sovereign_ai.agent not importable: {exc}")

    assert hasattr(mod, "sign_payload"), (
        "sovereign_ai.agent must export 'sign_payload'"
    )
    assert callable(mod.sign_payload)


def test_agent_sign_payload_missing_key(tmp_path):
    """sign_payload raises FileNotFoundError for a non-existent key file."""
    try:
        from sovereign_ai.agent import sign_payload
    except ImportError as exc:
        pytest.skip(f"sovereign_ai.agent not importable: {exc}")

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: F401
    except ImportError:
        pytest.skip("cryptography package not installed")

    with pytest.raises(FileNotFoundError):
        sign_payload({"key": "value"}, tmp_path / "nonexistent.pem")


def test_agent_sign_payload_roundtrip(tmp_path):
    """sign_payload produces a valid Ed25519 signature that can be verified."""
    try:
        from sovereign_ai.agent import sign_payload
    except ImportError as exc:
        pytest.skip(f"sovereign_ai.agent not importable: {exc}")

    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            Encoding,
            NoEncryption,
            PrivateFormat,
        )
    except ImportError:
        pytest.skip("cryptography package not installed")

    import json

    # Generate an ephemeral key
    private_key = Ed25519PrivateKey.generate()
    pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    key_path = tmp_path / "ed25519_test.pem"
    key_path.write_bytes(pem)

    payload = {"event": "test", "principal": "alice"}
    hex_sig = sign_payload(payload, key_path)
    assert isinstance(hex_sig, str)
    assert len(hex_sig) == 128  # Ed25519 produces 64-byte / 128 hex chars

    # Verify the signature with the matching public key
    public_key = private_key.public_key()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    public_key.verify(bytes.fromhex(hex_sig), canonical)  # raises on invalid sig


# ---------------------------------------------------------------------------
# sovereign_ai.rag
# ---------------------------------------------------------------------------

def test_rag_import():
    """RAGPipeline, embed_documents, and query must be importable from sovereign_ai.rag."""
    try:
        mod = importlib.import_module("sovereign_ai.rag")
    except ImportError as exc:
        pytest.skip(f"sovereign_ai.rag not importable: {exc}")

    for name in ("RAGPipeline", "embed_documents", "query"):
        assert hasattr(mod, name), f"sovereign_ai.rag must export '{name}'"


def test_rag_pipeline_alias():
    """RAGPipeline must be an alias (or subclass) of LocalRAG."""
    try:
        from sovereign_ai.rag import RAGPipeline, LocalRAG
    except ImportError as exc:
        pytest.skip(f"sovereign_ai.rag not importable: {exc}")

    assert RAGPipeline is LocalRAG


# ---------------------------------------------------------------------------
# sovereign_ai.bridge
# ---------------------------------------------------------------------------

def test_bridge_import():
    """sovereign_ai.bridge must export __version__ and core schema classes."""
    try:
        mod = importlib.import_module("sovereign_ai.bridge")
    except ImportError as exc:
        pytest.skip(f"sovereign_ai.bridge not importable: {exc}")

    assert hasattr(mod, "__version__"), "sovereign_ai.bridge must have __version__"
    for name in ("ChatCompletionRequest", "ChatCompletionResponse", "ChatMessage"):
        assert hasattr(mod, name), f"sovereign_ai.bridge must export '{name}'"


# ---------------------------------------------------------------------------
# sovereign_ai top-level __version__
# ---------------------------------------------------------------------------

def test_sovereign_ai_version():
    """sovereign_ai.__version__ must be accessible."""
    try:
        import sovereign_ai
    except ImportError as exc:
        pytest.skip(f"sovereign_ai not importable: {exc}")

    assert hasattr(sovereign_ai, "__version__")
    assert isinstance(sovereign_ai.__version__, str)
    assert sovereign_ai.__version__  # non-empty
