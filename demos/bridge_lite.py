import uvicorn
from fastapi import FastAPI, Request
from sovereign_ai import RAGPipeline, Config
import os

app = FastAPI(title="Sovereign OpenAI Bridge")

# Initialize Pipeline (using Healthcare clinic_a as default demo)
base_dir = os.path.join(os.getcwd(), "demos")
cfg = Config(
    db_path=os.path.join(base_dir, "healthcare", "clinic_a.db"),
    policy_path=os.path.join(base_dir, "healthcare", "policy.yaml"),
    tenant_id="clinic_a",
    roles=["doctor"],
    enable_verification=True
)
pipeline = RAGPipeline(cfg)

@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    """OpenAI-compatible endpoint for Sovereign RAG."""
    body = await request.json()
    messages = body.get("messages", [])
    if not messages:
        return {"error": "No messages provided"}
    
    query = messages[-1]["content"]
    
    # Extract sovereign context if sent in headers or body
    role = body.get("role", "doctor")
    intent = body.get("intent", "treatment")
    
    # Execute RAG
    result = await pipeline.ask(query, intent=intent)
    
    # Return OpenAI-formatted response
    return {
        "id": "sov-123",
        "object": "chat.completion",
        "created": 123456789,
        "model": "sovereign-rag-v1",
        "choices": [{
            "index": 0,
            "message": {
                "role": "assistant",
                "content": result.answer
            },
            "finish_reason": "stop"
        }],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "sovereign_metadata": result.metadata.get("verification", {})
    }

if __name__ == "__main__":
    print("🚀 Sovereign Bridge LITE starting on http://localhost:8001")
    print("🔗 OpenAI Compatible Endpoint: http://localhost:8001/v1/chat/completions")
    uvicorn.run(app, host="0.0.0.0", port=8001)
