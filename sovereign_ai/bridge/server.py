import os
import uvicorn
from fastapi import FastAPI, Request, Response, HTTPException, Depends, Header
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
# Use standard string for service name to avoid dependency version clashes
from .orchestrator import SovereignOrchestrator
from .schemas import ChatCompletionRequest, ChatCompletionResponse, TenantContext
from .security import SovereignIdentityHub

# OpenTelemetry Setup (Sovereign Observability)
OTLP_ENDPOINT = os.getenv("OTLP_ENDPOINT") # e.g. http://localhost:4318/v1/traces
resource = Resource(attributes={
    "service.name": "local-bridge",
    "version": "1.0.0-GA"
})

provider = TracerProvider(resource=resource)
if OTLP_ENDPOINT:
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=OTLP_ENDPOINT))
    provider.add_span_processor(processor)
trace.set_tracer_provider(provider)

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Orchestrator pool, health checks, and cache maintenance
    await orchestrator.start_health_checks()
    await orchestrator.start_cache_maintenance()
    yield
    # Shutdown: Clean up Orchestrator pool
    await orchestrator.close()

app = FastAPI(
    title="local-bridge",
    description="GAIP-2030 Enterprise Platform — Multi-tenant sovereign AI control plane",
    version="1.0.0-GA",
    lifespan=lifespan
)

FastAPIInstrumentor.instrument_app(app)

DEFAULT_MODEL = os.getenv("SOVEREIGN_MODEL", "qwen2.5:7b")
BACKEND_CLUSTER = os.getenv("BACKEND_CLUSTER") 
MASTER_SECRET = os.getenv("MASTER_GATEWAY_SECRET", "sov-default-secret-change-me")
PGVECTOR_URL = os.getenv("PGVECTOR_URL")
MAX_RAG_POOL = int(os.getenv("SOVEREIGN_RAG_MAX_POOL", "10"))
BASE_DIR = os.getenv("SOVEREIGN_DATA_DIR", "data/")

# Initialize Sovereign Components
orchestrator = SovereignOrchestrator(
    base_dir=BASE_DIR,
    default_model=DEFAULT_MODEL,
    backend_cluster=BACKEND_CLUSTER,
    max_rag_pool=MAX_RAG_POOL,
    vector_dsn=PGVECTOR_URL
)

from .metrics import metrics, generate_latest, CONTENT_TYPE_LATEST
from fastapi.responses import StreamingResponse, Response
from typing import Optional, Union, List

identity_hub = SovereignIdentityHub(master_secret=MASTER_SECRET, base_dir=BASE_DIR)

@app.get("/health")
def health():
    return {"status": "sovereign", "version": "1.0.0-GA", "multitenant": True}

@app.get("/metrics")
async def get_metrics(request: Request):
    """
    Expose Prometheus metrics gated by management IP allowlist AND Admin Token.
    """
    # 1. IP Allowlist
    allowed_ips = os.getenv("SOVEREIGN_METRICS_ALLOWLIST", "127.0.0.1,::1").split(",")
    client_ip = request.client.host
    
    # 2. Admin Token (Header or Bearer)
    admin_token = request.headers.get("X-Admin-Token")
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        admin_token = auth_header.replace("Bearer ", "")
    
    if client_ip not in allowed_ips and admin_token != MASTER_SECRET:
        raise HTTPException(status_code=403, detail="Access to /metrics is restricted to management network with Admin credentials")
    
    return Response(content=generate_latest(metrics.registry), media_type=CONTENT_TYPE_LATEST)

@app.post("/v1/admin/tenants")
async def provision_tenant(tenant_id: str, request: Request):
    """
    Provison a new tenant silo (Admin Only).
    """
    # Simple Admin-Token check for v1.0.0 Pilot
    admin_token = request.headers.get("X-Admin-Token")
    if admin_token != MASTER_SECRET: # For pilot, master secret acts as admin token
        raise HTTPException(status_code=401, detail="Unauthorized Admin access")
        
    tenant_path = os.path.join(BASE_DIR, tenant_id)
    if os.path.exists(tenant_path):
        return {"status": "exists", "path": tenant_path}
        
    try:
        os.makedirs(os.path.join(tenant_path, "policies"), exist_ok=True)
        os.makedirs(os.path.join(tenant_path, "cache"), exist_ok=True)
        # Create initial empty revocation list
        with open(os.path.join(tenant_path, "revocation_list.json"), "w") as f:
            json.dump({"revoked_identifiers": []}, f)
            
        print(f"🛡️  Provisioned new tenant silo: {tenant_id}")
        return {"status": "created", "tenant_id": tenant_id, "path": tenant_path}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Provisioning Failed: {e}")

@app.post("/v1/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    context: TenantContext = Depends(identity_hub.get_context)
):
    """
    OpenAI-compatible Chat Completion endpoint with Multi-Tenant Enforcement.
    """
    # Override principal from authenticated context
    request.sovereign_principal = context.principal
    
    try:
        response = await orchestrator.complete(request, tenant_id=context.tenant_id)
        
        if request.stream:
            return StreamingResponse(response, media_type="text/event-stream")
        else:
            return response
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sovereign Bridge Error: {e}")

def main():
    """CLI entry point to launch the gateway."""
    # Ensure base data dir exists
    if not os.path.exists(BASE_DIR):
        os.makedirs(BASE_DIR, exist_ok=True)
        
    port = int(os.getenv("PORT", 8000))
    print(f"🚀 Launching local-bridge (GAIP-2030 Enterprise) on port {port}...")
    print(f"🛡️  Data Root: {BASE_DIR}")
    print(f"🔐 Identity: Signed API Keys + Keycloak OIDC")
    
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    main()
