import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path
import yaml

from .store import Store
from .audit import AuditLogger
from .db_utils import get_db_status
from .config import DEFAULT_DB_PATH
from .schemas import AuditRecord

app = FastAPI(title="Sovereign Hub")

# Setup templates (we will put hub.html in sovereign_ai/assets)
BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "assets"))

# Global references that will be initialized by the CLI runner
db_path_global: str = DEFAULT_DB_PATH
password_global: Optional[str] = None
policy_path_global: Optional[str] = "policy.yaml"

@app.get("/", response_class=HTMLResponse)
async def read_dashboard(request: Request):
    """Serve the Sovereign Hub dashboard."""
    return templates.TemplateResponse(request, "hub.html", {})

@app.get("/api/status")
async def get_status():
    """Aggregate health and sovereignty status."""
    # 1. DB Status
    db_status = get_db_status(db_path_global, password_global)
    
    # 2. Audit Status
    audit_logger = AuditLogger() # Uses default log path
    is_valid, msg = audit_logger.verify_integrity()
    
    # 3. Stats (if accessible)
    stats = {"docs": 0, "chunks": 0}
    if db_status.get("accessible"):
        try:
            store = Store(db_path_global, password_global)
            stats["docs"] = store.conn.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
            stats["chunks"] = store.conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            store.close()
        except:
            pass

    return {
        "db": {
            "path": db_path_global,
            "encrypted": db_status.get("encrypted", False),
            "accessible": db_status.get("accessible", False),
            "stats": stats
        },
        "audit": {
            "integrity": is_valid,
            "message": msg
        },
        "sovereignty_score": 93 # Placeholder for v0.4.0 baseline
    }

@app.get("/api/logs", response_model=List[AuditRecord])
async def get_logs(limit: int = 50):
    """Fetch the recent compliance stream."""
    audit_logger = AuditLogger()
    logs = audit_logger.read_logs()
    # Return last 'limit' logs, newest first
    return logs[-limit:][::-1]

@app.get("/api/policy")
async def get_policy():
    """Read-only view of the active security policy."""
    if not os.path.exists(policy_path_global):
        return {"error": "Policy file not found", "path": policy_path_global}
    
    try:
        with open(policy_path_global, "r", encoding="utf-8") as f:
            content = yaml.safe_load(f)
            return {
                "path": policy_path_global,
                "content": content
            }
    except Exception as e:
        return {"error": str(e), "path": policy_path_global}

@app.post("/api/verify-audit")
async def verify_audit():
    """Manually trigger a full forensic verification."""
    audit_logger = AuditLogger()
    is_valid, msg = audit_logger.verify_integrity()
    return {"valid": is_valid, "message": msg}

def start_hub(db_path: str, password: Optional[str] = None, policy_path: str = "policy.yaml", host: str = "127.0.0.1", port: int = 8555):
    """Entry point for the CLI to start the Hub server."""
    global db_path_global, password_global, policy_path_global
    db_path_global = db_path
    password_global = password
    policy_path_global = policy_path
    
    import uvicorn
    uvicorn.run(app, host=host, port=port)
