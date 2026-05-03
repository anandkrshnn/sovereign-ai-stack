"""
tests/test_monorepo_consolidation.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Phase 1 Verification Suite — Monorepo Consolidation

Purpose:
    Confirm that all satellite-repo logic (local-rag, local-bridge,
    local-agent-v0.2, local-verify) is correctly consolidated into
    sovereign_ai.* and that the package surface is complete and coherent.

Run with:
    pytest tests/test_monorepo_consolidation.py -v

Run in certification mode:
    pytest tests/test_monorepo_consolidation.py -v --sovereign-cert
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Force NullKeyring globally so any keyring call in SecureKeyManager is a no-op
try:
    import keyring
    from keyring.backends.null import Keyring as NullKeyring
    keyring.set_keyring(NullKeyring())
except Exception:
    pass


# ---------------------------------------------------------------------------
# IMPORT SURFACE TESTS
# ---------------------------------------------------------------------------

class TestImportSurface:
    """[IMPORT-*] All consolidated packages must be importable cleanly."""

    @pytest.mark.sovereign(id="IMPORT-01")
    def test_top_level_package_imports(self):
        """sovereign_ai top-level must expose SovereignPipeline and Config."""
        from sovereign_ai import SovereignPipeline, Config  # noqa: F401
        assert SovereignPipeline is not None
        assert Config is not None

    @pytest.mark.sovereign(id="IMPORT-02")
    def test_rag_public_all(self):
        """sovereign_ai.rag __all__ must contain the 12 consolidated symbols."""
        import sovereign_ai.rag as rag_pkg
        required = {
            "LocalRAG", "AsyncLocalRAG",
            "RAGResponse", "SearchResult",
            "GovernedRetriever", "AsyncGovernedRetriever",
            "FTS5Retriever", "AsyncFTS5Retriever",
            "QwenGenerator",
            "SemanticCache",
            "PolicyEngine",
            "RAGAuditLogger",
        }
        missing = required - set(rag_pkg.__all__)
        assert not missing, f"Missing from sovereign_ai.rag.__all__: {missing}"

    @pytest.mark.sovereign(id="IMPORT-03")
    def test_rag_symbols_actually_importable(self):
        """Every symbol declared in __all__ must be resolvable (no ImportError)."""
        import sovereign_ai.rag as rag_pkg
        for name in rag_pkg.__all__:
            obj = getattr(rag_pkg, name, None)
            assert obj is not None, f"sovereign_ai.rag.{name} is in __all__ but not importable"

    @pytest.mark.sovereign(id="IMPORT-04")
    def test_agent_forensics_exports(self):
        """agent.forensics must export AuditChainManager, SecureKeyManager, VaultContext."""
        from sovereign_ai.agent.forensics import (
            AuditChainManager,
            SecureKeyManager,
            VaultContext,
        )  # noqa: F401
        assert AuditChainManager is not None
        assert SecureKeyManager is not None
        assert VaultContext is not None

    @pytest.mark.sovereign(id="IMPORT-05")
    def test_bridge_package_import(self):
        """sovereign_ai.bridge must be importable."""
        import sovereign_ai.bridge  # noqa: F401

    @pytest.mark.sovereign(id="IMPORT-06")
    def test_bridge_submodules_importable(self):
        """Core bridge sub-modules must all import cleanly."""
        from sovereign_ai.bridge import orchestrator  # noqa: F401
        from sovereign_ai.bridge import security      # noqa: F401
        from sovereign_ai.bridge import schemas       # noqa: F401


# ---------------------------------------------------------------------------
# AUDIT CHAIN TESTS  (sovereign_ai.agent.forensics.AuditChainManager)
# ---------------------------------------------------------------------------

class TestAuditChain:
    """[CHAIN-*] AuditChainManager hash-chain correctness."""

    def _write_chain(self, log_path: Path, entries: list) -> str:
        """Helper: write a valid hash-chained JSONL file and return final hash."""
        from sovereign_ai.agent.forensics import AuditChainManager
        prev_hash = AuditChainManager.GENESIS_HASH
        with open(log_path, "w", encoding="utf-8") as f:
            for entry in entries:
                next_hash = AuditChainManager.calculate_next_hash(prev_hash, entry)
                record = {**entry, "chain_hash": next_hash}
                f.write(json.dumps(record) + "\n")
                prev_hash = next_hash
        return prev_hash

    @pytest.mark.sovereign(id="CHAIN-01")
    def test_write_and_verify_chain_roundtrip(self, tmp_path):
        """A correctly written chain must pass verify_chain."""
        from sovereign_ai.agent.forensics import AuditChainManager
        log_path = tmp_path / "audit.jsonl"
        entries = [
            {"event": "policy_check", "action": "allow", "principal": "analyst@alpha"},
            {"event": "rag_query",    "query": "What is sovereign AI?"},
            {"event": "agent_step",   "tool": "search", "result": "ok"},
        ]
        self._write_chain(log_path, entries)
        assert AuditChainManager.verify_chain(log_path) is True

    @pytest.mark.sovereign(id="CHAIN-02")
    def test_tamper_detection_breaks_chain(self, tmp_path):
        """Mutating a field in any log entry must cause verify_chain to return False."""
        from sovereign_ai.agent.forensics import AuditChainManager
        log_path = tmp_path / "audit.jsonl"
        entries = [
            {"event": "policy_check", "action": "allow"},
            {"event": "rag_query",    "query": "original query"},
        ]
        self._write_chain(log_path, entries)

        # Tamper: overwrite second line with a mutated entry
        lines = log_path.read_text(encoding="utf-8").splitlines()
        second = json.loads(lines[1])
        second["query"] = "TAMPERED query"
        lines[1] = json.dumps(second)
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        assert AuditChainManager.verify_chain(log_path) is False

    @pytest.mark.sovereign(id="CHAIN-03")
    def test_anchor_save_and_verify(self, tmp_path):
        """save_anchor must produce a .anchor file; verify_anchor must confirm it."""
        from sovereign_ai.agent.forensics import AuditChainManager
        log_path = tmp_path / "audit.jsonl"
        entries = [{"event": "bridge_forward", "status": "success"}]
        final_hash = self._write_chain(log_path, entries)

        AuditChainManager.save_anchor(log_path, last_hash=final_hash)
        assert (tmp_path / "audit.anchor").exists()
        assert AuditChainManager.verify_anchor(log_path, last_hash=final_hash) is True

    @pytest.mark.sovereign(id="CHAIN-04")
    def test_empty_log_returns_genesis_hash(self, tmp_path):
        """An empty (non-existent) log must return the GENESIS_HASH."""
        from sovereign_ai.agent.forensics import AuditChainManager
        log_path = tmp_path / "empty_audit.jsonl"
        result = AuditChainManager.get_last_hash(log_path)
        assert result == AuditChainManager.GENESIS_HASH

    @pytest.mark.sovereign(id="CHAIN-05")
    def test_calculate_next_hash_is_deterministic(self):
        """calculate_next_hash must be purely deterministic given same inputs."""
        from sovereign_ai.agent.forensics import AuditChainManager
        entry = {"event": "test", "value": 42}
        h1 = AuditChainManager.calculate_next_hash("genesis", entry)
        h2 = AuditChainManager.calculate_next_hash("genesis", entry)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex digest


# ---------------------------------------------------------------------------
# RAG MODULE TESTS  (sovereign_ai.rag.*)
# ---------------------------------------------------------------------------

class TestRAGConsolidation:
    """[RAG-*] LocalRAG API and RAGResponse contract."""

    @pytest.mark.sovereign(id="RAG-01")
    def test_local_rag_ask_returns_rag_response(self, temp_db, mock_generator):
        """LocalRAG.ask() with a seeded DB must return a typed RAGResponse."""
        from sovereign_ai.rag.main import LocalRAG
        from sovereign_ai.rag.store import Store
        from sovereign_ai.rag.schemas import RAGResponse

        # Seed with one document
        store = Store(temp_db)
        store.add_document("doc-001", "Sovereign AI ensures local data residency and zero-trust attestation.", "public")
        store.close()

        rag = LocalRAG(temp_db)
        rag.generator = mock_generator
        result = rag.ask("What is sovereign AI?")
        rag.close()

        assert isinstance(result, RAGResponse)
        assert isinstance(result.answer, str)
        assert len(result.answer) > 0

    @pytest.mark.sovereign(id="RAG-02")
    def test_rag_response_schema_fields(self, temp_db, mock_generator):
        """RAGResponse must carry .answer, .sources, and .model_name."""
        from sovereign_ai.rag.main import LocalRAG
        from sovereign_ai.rag.store import Store
        from sovereign_ai.rag.schemas import RAGResponse

        store = Store(temp_db)
        store.add_document("doc-002", "The PTV protocol binds Ed25519 keys to agent identities at runtime.", "internal")
        store.close()

        rag = LocalRAG(temp_db)
        rag.generator = mock_generator
        result = rag.ask("Explain the PTV protocol.")
        rag.close()

        assert hasattr(result, "answer")
        assert hasattr(result, "sources")
        assert hasattr(result, "model_name")

    @pytest.mark.sovereign(id="RAG-03")
    def test_rag_fail_closed_on_empty_db(self, temp_db, mock_generator):
        """LocalRAG must return an [Insufficient Local Context] refusal on empty DB."""
        from sovereign_ai.rag.main import LocalRAG

        rag = LocalRAG(temp_db)
        rag.generator = mock_generator
        result = rag.ask("This query has no matching documents.")
        rag.close()

        assert "Insufficient Local Context" in result.answer
        assert result.sources == []

    @pytest.mark.sovereign(id="RAG-04")
    def test_rag_consolidation_docstring_present(self):
        """sovereign_ai.rag.__doc__ must mention the consolidation notice."""
        import sovereign_ai.rag as rag_pkg
        assert rag_pkg.__doc__ is not None
        assert "local-rag" in rag_pkg.__doc__
        assert "deprecated" in rag_pkg.__doc__.lower()


# ---------------------------------------------------------------------------
# BRIDGE MODULE TESTS  (sovereign_ai.bridge.*)
# ---------------------------------------------------------------------------

class TestBridgeConsolidation:
    """[BRIDGE-*] Bridge orchestrator and security layer importable and coherent."""

    @pytest.mark.sovereign(id="BRIDGE-01")
    def test_bridge_schemas_importable(self):
        """Bridge schemas (AgentRequest, AgentResponse or similar) must be importable."""
        from sovereign_ai.bridge import schemas
        assert schemas is not None

    @pytest.mark.sovereign(id="BRIDGE-02")
    def test_bridge_security_importable(self):
        """Bridge security module must be importable (rate-limiting, auth guards)."""
        from sovereign_ai.bridge import security
        assert security is not None

    @pytest.mark.sovereign(id="BRIDGE-03")
    def test_bridge_orchestrator_importable(self):
        """Bridge orchestrator (28 KB — the core logic) must be importable."""
        from sovereign_ai.bridge import orchestrator
        assert orchestrator is not None


# ---------------------------------------------------------------------------
# PACKAGE VERSION TESTS
# ---------------------------------------------------------------------------

class TestPackageVersions:
    """[PKG-*] Version strings and package metadata."""

    @pytest.mark.sovereign(id="PKG-01")
    def test_agent_version_string_present(self):
        """sovereign_ai.agent must declare a __version__."""
        import sovereign_ai.agent as agent_pkg
        assert hasattr(agent_pkg, "__version__")
        assert isinstance(agent_pkg.__version__, str)
        assert len(agent_pkg.__version__) > 0

    @pytest.mark.sovereign(id="PKG-02")
    def test_forensics_consolidation_docstring_present(self):
        """forensics __init__.__doc__ must reference the consolidation note."""
        from sovereign_ai.agent import forensics
        assert forensics.__doc__ is not None
        assert "local-agent" in forensics.__doc__ or "consolidation" in forensics.__doc__.lower()


# ---------------------------------------------------------------------------
# END-TO-END SMOKE TEST  (rag → forensics chain)
# ---------------------------------------------------------------------------

class TestEndToEndSmoke:
    """
    [E2E-*] Lightweight end-to-end: a RAG query result gets appended to an
    audit chain and the chain remains valid.  No Ollama required (mocked).
    """

    @pytest.mark.sovereign(id="E2E-01")
    def test_rag_result_appended_to_audit_chain(self, tmp_path, mock_generator):
        """
        1. Seed RAG DB with one document.
        2. Run LocalRAG.ask() with mocked generator.
        3. Append the answer as an audit event to a JSONL chain.
        4. Verify the chain is intact.
        """
        import sqlite3
        from sovereign_ai.rag.main import LocalRAG
        from sovereign_ai.rag.store import Store
        from sovereign_ai.agent.forensics import AuditChainManager

        db_path = str(tmp_path / "rag.db")
        log_path = tmp_path / "audit.jsonl"

        # Seed
        store = Store(db_path)
        store.add_document(
            "doc-e2e",
            "Sovereign AI stacks bind hardware attestation to agent decision traces.",
            "public",
        )
        store.close()

        # Query
        rag = LocalRAG(db_path)
        rag.generator = mock_generator
        result = rag.ask("What does the sovereign AI stack bind?")
        rag.close()

        # Audit
        prev_hash = AuditChainManager.GENESIS_HASH
        event = {
            "event": "rag_query_completed",
            "query": "What does the sovereign AI stack bind?",
            "model": result.model_name,
            "num_sources": len(result.sources),
            "answer_preview": result.answer[:80],
        }
        next_hash = AuditChainManager.calculate_next_hash(prev_hash, event)
        record = {**event, "chain_hash": next_hash}
        log_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

        assert AuditChainManager.verify_chain(log_path) is True
        assert result.model_name == "mock-qwen-1.5b"
