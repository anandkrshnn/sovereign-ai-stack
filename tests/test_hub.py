import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from local_rag.hub import app
from local_rag.schemas import AuditRecord, PolicyDecision
import os

client = TestClient(app)

@pytest.fixture
def mock_audit_logger():
    with patch("local_rag.hub.AuditLogger") as mock:
        instance = mock.return_value
        instance.verify_integrity.return_value = (True, "Forensic chain intact.")
        instance.read_logs.return_value = []
        yield instance

@pytest.fixture
def mock_db_utils():
    with patch("local_rag.hub.get_db_status") as mock:
        mock.return_value = {
            "exists": True, 
            "encrypted": True, 
            "accessible": True,
            "stats": {"docs": 10, "chunks": 50}
        }
        yield mock

def test_hub_dashboard_accessible():
    """Verify the dashboard HTML is served."""
    # Ensure assets directory exists in the environment
    os.makedirs("local_rag/assets", exist_ok=True)
    if not os.path.exists("local_rag/assets/hub.html"):
        with open("local_rag/assets/hub.html", "w") as f:
            f.write("<html>Sovereign Hub</html>")
            
    response = client.get("/")
    assert response.status_code == 200
    assert "Sovereign Hub" in response.text

def test_api_status(mock_audit_logger, mock_db_utils):
    """Test the aggregate status endpoint."""
    with patch("local_rag.hub.Store") as mock_store:
        store_instance = mock_store.return_value
        store_instance.conn.execute.return_value.fetchone.return_value = [10]
        
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["db"]["encrypted"] is True
        assert data["audit"]["integrity"] is True
        assert data["db"]["stats"]["docs"] == 10

def test_api_logs(mock_audit_logger):
    """Test the compliance stream endpoint with valid schema."""
    record = AuditRecord(
        event_id="abc-123",
        principal="test-user",
        query_hash="hash",
        query_preview="What is...",
        decision=PolicyDecision(action="allow", reason="Rules pass"),
        candidate_count=5,
        allowed_count=5,
        denied_count=0,
        curr_hash="hash-123",
        sequence_number=1
    )
    mock_audit_logger.read_logs.return_value = [record]
    
    response = client.get("/api/logs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["principal"] == "test-user"
    assert data[0]["decision"]["action"] == "allow"

def test_api_verify_audit(mock_audit_logger):
    """Test manual verification trigger."""
    response = client.post("/api/verify-audit")
    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert "Forensic chain intact" in response.json()["message"]

def test_api_policy_not_found():
    """Test policy view when file missing."""
    with patch("os.path.exists", return_value=False):
        response = client.get("/api/policy")
        assert response.status_code == 200
        assert "error" in response.json()
