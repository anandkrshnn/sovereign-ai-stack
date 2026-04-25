import pytest
import sqlite3
import shutil
import os
import json
import time
from pathlib import Path
from unittest.mock import MagicMock

from local_rag.store import Store
from local_rag.retriever import FTS5Retriever
from local_rag.main import LocalRAG
from local_rag.generator import QwenGenerator
from local_rag.pipeline import RAGPipeline, Config
from local_rag.schemas import Document

def pytest_addoption(parser):
    parser.addoption("--sovereign-cert", action="store_true", help="Run in GAIP-2030 certification mode")

@pytest.fixture(scope="session")
def sovereign_cert(request):
    return request.config.getoption("--sovereign-cert")

@pytest.fixture(scope="function")
def sovereign_test_env(tmp_path):
    """Create isolated test environment with multi-tenant setup (v1.0.0-GA)."""
    env = {
        "base_dir": tmp_path,
        "tenants": {},
    }
    
    # Create tenants with overlapping but isolated data
    for tenant_id in ["tenant_alpha", "tenant_beta", "tenant_gamma"]:
        tenant_dir = tmp_path / tenant_id
        tenant_dir.mkdir()
        
        db_path = tenant_dir / "rag.db"
        audit_path = tenant_dir / "audit.jsonl"
        cache_dir = tenant_dir / "cache"
        policy_path = tenant_dir / "policy.yaml"
        
        # Default "Allow-Self" policy
        with open(policy_path, "w") as f:
            f.write(f"""
version: "1.0.0-GA"
allow:
  - tenant_id: "{tenant_id}"
    roles: ["user", "admin", "analyst"]
    classifications: ["public", "internal", "confidential", "secret", "all"]
""")

        config = Config(
            db_path=str(db_path),
            policy_path=str(policy_path),
            tenant_id=tenant_id,
            principal=f"user@{tenant_id}",
            use_cache=True,
            cache_dir=str(cache_dir)
        )
        
        env["tenants"][tenant_id] = {
            "config": config,
            "db_path": db_path,
            "audit_path": audit_path,
            "cache_dir": cache_dir
        }
    
    return env

# Global results collection for certification report
CERT_RESULTS = []

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    
    if report.when == "call" and item.config.getoption("--sovereign-cert"):
        marker = item.get_closest_marker("sovereign")
        if marker:
            test_id = item.name
            # Try to get test_id from marker if it exists (e.g. @pytest.mark.sovereign(id="ISO-001"))
            if marker.kwargs.get("id"):
                test_id = marker.kwargs["id"]
                
            CERT_RESULTS.append({
                "test_id": test_id,
                "node_id": item.nodeid,
                "outcome": report.outcome,
                "duration": report.duration,
                "error": str(report.longrepr) if report.failed else None
            })

def pytest_sessionfinish(session, exitstatus):
    if session.config.getoption("--sovereign-cert"):
        output_path = Path("tests/certification/results.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(CERT_RESULTS, f, indent=2)

@pytest.fixture
def temp_db(tmp_path):
    """Fixture for a temporary SQLite database."""
    db_path = tmp_path / "test_rag.db"
    return str(db_path)

@pytest.fixture
def store(temp_db):
    """Fixture for a clean Store instance."""
    s = Store(temp_db)
    yield s
    s.close()

@pytest.fixture
def retriever(temp_db):
    """Fixture for a clean FTS5Retriever instance."""
    r = FTS5Retriever(temp_db)
    yield r
    r.close()

@pytest.fixture
def mock_generator():
    """Fixture for a mocked QwenGenerator."""
    mock = MagicMock(spec=QwenGenerator)
    mock.model_name = "mock-qwen-1.5b"
    mock.generate.return_value = "Mocked answer based on context."
    mock.stream_generate.return_value = iter(["Mocked ", "streaming ", "answer."])
    return mock

@pytest.fixture
def rag_instance(temp_db, mock_generator):
    """Fixture for LocalRAG with a mocked generator."""
    rag = LocalRAG(temp_db)
    rag.generator = mock_generator
    yield rag
    rag.close()
