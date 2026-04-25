from fastapi import FastAPI, Request
from local_rag import RAGPipeline, Config
import asyncio
import os
import time

app = FastAPI(title="local-bridge-demo", version="1.1.0")

# Local Anchors: Simulated audit tip
def get_audit_tip():
    return f"sov-anchor-{int(time.time())}-{os.urandom(2).hex()}"

@app.middleware("http")
async def sovereign_headers(request: Request, call_next):
    # Principal Extraction: Header preferred, then body fallback
    principal = request.headers.get("x-sovereign-principal", "guest")
    request.state.principal = principal
    
    response = await call_next(request)
    
    # Egress: Add Sovereign Audit Tip (Forensic Trace)
    response.headers["x-sovereign-tip"] = get_audit_tip()
    return response

# Global cache for pipelines to avoid re-initializing if not needed (optional for demo)
_pipelines = {}

async def get_pipeline(role: str):
    if role not in _pipelines:
        # Resolve paths relative to where this is run (assume local-bridge root)
        # For demo, we default to the healthcare scenario
        base_path = os.path.join(os.getcwd(), "..", "local-rag", "demos", "healthcare")
        db_path = os.path.join(base_path, "clinic_a.db")
        policy_path = os.path.join(base_path, "policy.yaml")
        
        cfg = Config(
            db_path=db_path if os.path.exists(db_path) else None,
            policy_path=policy_path if os.path.exists(policy_path) else None,
            tenant_id="clinic_a",
            roles=[role],
            enable_verification=True
        )
        _pipelines[role] = RAGPipeline(cfg)
    return _pipelines[role]

@app.get("/health")
async def health():
    return {"status": "sovereign", "bridge": "active"}

@app.post("/v1/chat/completions")
async def chat(request: dict, req: Request):
    """OpenAI-compatible Chat Completion endpoint."""
    messages = request.get("messages", [])
    if not messages:
        return {"error": "No messages provided"}, 400
        
    query = messages[-1]["content"]
    
    # Extract principal from state (set by middleware)
    principal_role = req.state.principal
    
    # Get pipeline for this role
    pipeline = await get_pipeline(principal_role)
    
    # Execute RAG Pipeline
    result = await pipeline.ask(query)
    
    # Format as OpenAI response
    return {
        "id": f"chatcmpl-{os.urandom(4).hex()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": "sovereign-rag",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant", 
                "content": result.answer
            },
            "finish_reason": "stop"
        }],
        "usage": {
            "prompt_tokens": len(query) // 4,
            "completion_tokens": len(result.answer) // 4,
            "total_tokens": (len(query) + len(result.answer)) // 4
        },
        "metadata": result.metadata.get("verification")
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
