import os
import sys
import json
import asyncio
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

# Add root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sovereign_ai import SovereignPipeline, Config

app = FastAPI(title="Sovereign RAG Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache pipelines to avoid re-loading models
pipelines = {}

class RAGRequest(BaseModel):
    tenant_id: str
    roles: List[str]
    classifications: List[str]
    query: str
    intent: str

@app.post("/ask")
async def ask_rag(req: RAGRequest):
    # Determine DB and Policy path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    if req.tenant_id == "clinic_a":
        db = os.path.join(base_dir, "healthcare", "clinic_a.db")
        policy = os.path.join(base_dir, "healthcare", "policy.yaml")
    elif req.tenant_id == "acme_corp":
        db = os.path.join(base_dir, "finance", "finance.db")
        policy = os.path.join(base_dir, "finance", "policy.yaml")
    else:
        db = os.path.join(base_dir, "engineering", "eng.db")
        policy = os.path.join(base_dir, "engineering", "policy.yaml")

    pipe_key = f"{req.tenant_id}_{'-'.join(req.roles)}"
    
    if pipe_key not in pipelines:
        cfg = Config(
            db_path=db,
            policy_path=policy,
            tenant_id=req.tenant_id,
            roles=req.roles,
            classifications=req.classifications,
            use_reranker=False
        )
        pipelines[pipe_key] = SovereignPipeline(cfg)
    
    pipe = pipelines[pipe_key]
    res = await pipe.ask(req.query, intent=req.intent)
    
    return {
        "answer": res.answer,
        "sources": [{"text": s.text, "doc_id": s.doc_id} for s in res.sources],
        "is_denied": "[Sovereign Access Denied]" in res.answer or "[Sovereign Privacy Guardrail]" in res.answer
    }

@app.get("/", response_class=HTMLResponse)
async def get_gui():
    with open(os.path.join(os.path.dirname(__file__), "gui.html"), "r", encoding="utf-8") as f:
        return f.read()

if __name__ == "__main__":
    print("\n[Sovereign Dashboard] Starting GUI Server on http://127.0.0.1:8888")
    uvicorn.run(app, host="127.0.0.1", port=8888)
