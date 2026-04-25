import os
import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from localagent.core_loop import LocalAgent
from localagent.forensics.vault_context import VaultContext
from localagent.api.bridge import BridgeSecurityManager
import uvicorn
import random
from localagent.config import Config
from contextlib import asynccontextmanager

# Global State: Total singleton isolation
current_agent = None
current_vault_name = "default"
transition_lock = asyncio.Lock()

# Volatile session store for pending confirmations
pending_requests: Dict[str, dict] = {}

# Phase 3: SSE Event Bus for real-time synchronization
class EventBus:
    def __init__(self):
        self.subscribers: List[asyncio.Queue] = []

    async def subscribe(self):
        queue = asyncio.Queue()
        self.subscribers.append(queue)
        try:
            yield queue
        finally:
            self.subscribers.remove(queue)

    async def broadcast(self, event_type: str, data: Any):
        event = {"type": event_type, "data": data, "timestamp": datetime.now().isoformat()}
        for queue in self.subscribers:
            await queue.put(event)

event_bus = EventBus()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # PRE-WARMING: Load embedder and default agent once on startup
    try:
        from localagent.memory import get_embedder
        print("Pre-warming embedding model...")
        await asyncio.to_thread(get_embedder)
        print("Embedding model ready.")
        
        # Proactively load default agent in background to warm up first interaction
        asyncio.create_task(asyncio.to_thread(LocalAgent))
        
        # Phase 4: Start IPC Bridge Listener for CLI Comms
        from localagent.cli.ipc import start_ipc_bridge
        asyncio.create_task(start_ipc_bridge())
        
    except Exception as e:
        print(f"Warning: Failed to pre-warm components: {e}")
    
    yield
    
    if current_agent:
        try:
            current_agent.close()
        except: pass

app = FastAPI(title="LocalAgent Dashboard", lifespan=lifespan)

# --- Bridge DoS Protection: reject payloads > 1.04 MB before HMAC evaluation ---
# Spec §3: "Payloads > 1.04MB trigger immediate PAYLOAD_TOO_LARGE drop states at TCP ingress."
from starlette.middleware.base import BaseHTTPMiddleware

_BRIDGE_MAX_BYTES = 1_048_576  # 1.04 MB hard limit


class PayloadSizeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and "bridge" in request.url.path:
            if len(await request.body()) > 1_048_576:  # 1.04MB
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=413,
                    content={"error": "PAYLOAD_TOO_LARGE", "detail": "Payload too large"}
                )
        return await call_next(request)


app.add_middleware(PayloadSizeMiddleware)

# For modular v0.2 structure, we look inside the 'web' subdirectory
BASE_DIR = Path(__file__).resolve().parent / "web"
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

config = Config.default()
bridge_security = BridgeSecurityManager(secret=config.bridge_secret)

async def apply_jitter(response_type: str = "local"):
    """
    Injects non-deterministic delay to mitigate timing-based side-channel attacks.
    Local (dashboard): 0-20ms
    Bridge (remote): 50-200ms
    """
    if response_type == "bridge":
        delay = random.uniform(*config.jitter_bridge_ms_range)
    else:
        delay = random.uniform(*config.jitter_local_ms_range)
    await asyncio.sleep(delay)

async def get_agent_async():
    """Thread-safe lazy initializer for the default agent."""
    global current_agent
    async with transition_lock:
        if current_agent is None:
            # Load default agent in a separate thread
            current_agent = await asyncio.to_thread(LocalAgent)
        return current_agent

def get_agent():
    """Sync fallback for legacy calls (should be minimized)."""
    global current_agent
    if current_agent is None:
        current_agent = LocalAgent()
    return current_agent

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    agent = await get_agent_async()
    stats = await asyncio.to_thread(agent.get_stats)
    
    # Add memory item counts
    try:
        items = await asyncio.to_thread(agent.memory_service.lancedb_store.get_memory_items)
        stats["memory_items"] = {
            "total": len(items),
            "pending": len([i for i in items if i["status"] == "candidate"]),
            "approved": len([i for i in items if i["status"] == "approved"])
        }
    except:
        stats["memory_items"] = {"total": 0, "pending": 0, "approved": 0}
        
    return templates.TemplateResponse(
        request=request,
        name="index.html", 
        context={
            "stats": stats,
            "current_vault": current_vault_name
        }
    )

@app.get("/vaults/list")
async def list_vaults():
    """Scan the local vaults directory."""
    vault_root = Path("vaults")
    vault_root.mkdir(exist_ok=True)
    
    vaults = [d.name for d in vault_root.iterdir() if d.is_dir()]
    return {"vaults": vaults, "current": current_vault_name}

@app.post("/vaults/create")
async def create_vault(request: Request):
    global current_agent, current_vault_name
    data = await request.json()
    name = data.get("name", "new_vault")
    password = data.get("password")

    vault_path = f"vaults/{name}"

    try:
        # Close previous agent safely
        if current_agent is not None:
            try:
                current_agent.close()
            except:
                pass
            current_agent = None

        current_agent = await asyncio.to_thread(
            LocalAgent, vault_root=vault_path, password=password
        )
        current_vault_name = name
        return {"status": "created", "vault": name}
    except Exception as e:
        await apply_jitter("local")
        return {"status": "error", "message": str(e)}

@app.post("/vaults/unlock")
async def unlock_vault(request: Request):
    global current_agent, current_vault_name
    data = await request.json()
    name = data.get("name")
    password = data.get("password")

    vault_path = f"vaults/{name}"

    try:
        if current_agent is not None:
            try:
                current_agent.close()
            except:
                pass
            current_agent = None

        current_agent = await asyncio.to_thread(
            LocalAgent, vault_root=vault_path, password=password
        )
        current_vault_name = name
        return {"status": "unlocked", "vault": name}
    except Exception as e:
        await apply_jitter("local") # Mitigation for brute-force password attempts
        return {"status": "error", "message": str(e)}

@app.post("/vaults/lock")
async def lock_vault():
    """Securely clear agent instance and release file handles."""
    global current_agent, current_vault_name
    async with transition_lock:
        if current_agent:
            try:
                current_agent.close()
            except: pass
            current_agent = None
            current_vault_name = "default"
        return {"status": "locked", "message": "Vault locked and session cleared."}

@app.post("/chat/stream")
async def chat_stream(request: Request):
    global current_agent, current_vault_name

    if not current_agent:
        async def no_vault():
            yield f"data: {json.dumps({'type': 'chunk', 'content': 'No vault unlocked. Please create or unlock a vault first.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_vault(), media_type="text/event-stream")

    data = await request.json()
    user_input = data.get("message", "").strip()

    if not user_input:
        async def empty():
            yield f"data: {json.dumps({'type': 'chunk', 'content': 'Please enter a message.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(empty(), media_type="text/event-stream")

    async def event_generator():
        try:
            # Immediate, informative cold-start message
            yield f"data: {json.dumps({'type': 'status', 'content': '🔄 Decrypting vault & loading model... (first response can take 15-60s on CPU)'})}\n\n"
            await event_bus.broadcast("status", "Agent is thinking (decrypting vault)...")

            # 180s timeout for first inference
            full_response = await asyncio.wait_for(
                asyncio.to_thread(current_agent.chat, user_input),
                timeout=180.0
            )

            if not full_response:
                yield f"data: {json.dumps({'type': 'chunk', 'content': 'No response from model.'})}\n\n"
            elif isinstance(full_response, dict) and full_response.get("requires_confirmation"):
                # Bridge: Save the request so it can be confirmed via /confirm
                req_id = full_response.get("request_id")
                if req_id:
                    pending_requests[req_id] = {
                        "intent": full_response.get("intent"),
                        "resource": full_response.get("resource"),
                        "tool_name": full_response.get("tool_name"),
                        "arguments": full_response.get("arguments"),
                        "message": user_input,
                        "risk_score": full_response.get("risk_score", 0.5)
                    }
                
                # Phase 3: Synchronize across all connected dashboards
                await event_bus.broadcast("airlock_required", full_response)
                
                # Handle permission requirement correctly
                yield f"data: {json.dumps({'type': 'permission_required', 'data': full_response})}\n\n"
                yield "data: [DONE]\n\n"
                return
            else:
                # Streaming chunks for normal string responses
                full_str = str(full_response)
                for i in range(0, len(full_str), 3):
                    chunk = full_str[i:i+3]
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                    await asyncio.sleep(0.02)

            yield "data: [DONE]\n\n"
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'status', 'content': 'Response timed out (180s). Try a shorter message.'})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'status', 'content': f'Error: {str(e)}'})}\n\n"
            yield "data: [DONE]\n\n"
        except asyncio.TimeoutError:
            yield f"data: {json.dumps({'type': 'chunk', 'content': 'Response timed out (180s). Initial load is slow.'})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'chunk', 'content': f'Error: {str(e)}'})}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/confirm")
async def confirm_permission(request: Request):
    agent = await get_agent_async()
    data = await request.json()
    request_id = data.get("request_id")
    approved = data.get("approved", False)

    if not request_id or request_id not in pending_requests:
        await apply_jitter("local")
        return {"success": False, "message": "Invalid or expired request ID. Please try sending your instruction again."}

    pending = pending_requests.pop(request_id)
    
    try:
        result = agent.broker.confirm_permission(
            intent=pending["intent"], 
            resource=pending["resource"], 
            approved=approved
        )
    except Exception as e:
        return {"success": False, "message": f"Broker error: {str(e)}"}

    if not result.get("granted"):
        await event_bus.broadcast("permission_denied", {"request_id": request_id})
        return {"success": False, "message": "Permission denied by user."}

    await event_bus.broadcast("permission_granted", {"request_id": request_id})

    try:
        # Re-execute the tool directly now that it's approved
        # We pass the token from the broker confirmation
        final_result = await asyncio.to_thread(
            agent._execute_tool, 
            pending["tool_name"], 
            pending["arguments"], 
            token=result.get("token")
        )
        return {
            "success": True,
            "response": str(final_result),
            "approval_count": result.get("approval_count", 0),
            "pattern_learned": result.get("pattern_learned", False),
            "message": result.get("message", "Permission granted.")
        }
    except Exception as e:
        return {"success": False, "message": f"Execution error: {str(e)}"}

    except Exception as e:
        return {"status": "offline", "message": str(e)}

@app.get("/memory/items")
async def get_memory_items(status: Optional[str] = None):
    agent = await get_agent_async()
    try:
        items = await asyncio.to_thread(agent.memory_service.lancedb_store.get_memory_items, status=status)
        return {"success": True, "items": items}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/memory/action/{memory_id}")
async def memory_action(memory_id: str, request: Request):
    agent = await get_agent_async()
    data = await request.json()
    action = data.get("action") # "approve", "forget", "reject"
    
    try:
        if action == "forget":
            await asyncio.to_thread(agent.memory_service.lancedb_store.delete_memory_item, memory_id)
        elif action == "approve":
            await asyncio.to_thread(agent.memory_service.lancedb_store.update_memory_status, memory_id, "approved")
        elif action == "reject":
            await asyncio.to_thread(agent.memory_service.lancedb_store.update_memory_status, memory_id, "rejected")
        
        # --- MILESTONE 4: REFRESH HOT CACHE ---
        await asyncio.to_thread(agent.memory_service.refresh_hot_cache)
        
        return {"success": True, "message": f"Action {action} applied to {memory_id}"}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/memory/optimize")
async def optimize_memory():
    agent = await get_agent_async()
    try:
        # Get recent episodes and force a promotion cycle
        episodes = await asyncio.to_thread(agent.memory_service.lancedb_store.get_recent_episodes, limit=50)
        for ep in episodes:
            await asyncio.to_thread(
                agent.memory_service.promotion_pipeline.run_cycle, 
                ep.get("episode_id"), 
                ep.get("content_text", "")
            )
        return {"success": True, "message": "Memory consolidation complete."}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/stats")
async def get_stats():
    agent = await get_agent_async()
    stats = await asyncio.to_thread(agent.get_stats)
    
    import requests
    try:
        endpoint = agent.config.ollama_endpoint.replace("localhost", "127.0.0.1")
        res = await asyncio.to_thread(requests.get, f"{endpoint}/api/tags", timeout=1)
        stats["ollama_online"] = (res.status_code == 200)
    except:
        stats["ollama_online"] = False
        stats["vault_active"] = (current_agent is not None)
    stats["vault_name"] = current_vault_name
    stats["active_model"] = agent.model
    
    return stats

@app.get("/audit")
async def get_audit():
    agent = await get_agent_async()
    audit_path = Path(agent.vault.audit_log)
    if not audit_path.exists():
        return {"audit": []}
    
    audit = []
    try:
        with open(audit_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            for line in reversed(lines):
                line = line.strip()
                if not line: continue
                try:
                    if agent.vault.key_manager and agent.vault.key_manager.is_encrypted():
                        line = agent.vault.key_manager.decrypt(line)
                    entry = json.loads(line)
                    audit.append({
                        "timestamp": entry.get("timestamp"),
                        "intent": entry.get("intent"),
                        "resource": entry.get("resource"),
                        "granted": entry.get("granted"),
                        "reason": entry.get("reason", ""),
                        "trace_id": entry.get("trace_id")
                    })
                    if len(audit) >= 50: break
                except: continue
        return {"audit": audit}
    except:
        return {"audit": []}

@app.get("/trust_status")
async def get_trust_status():
    """Retrieve persistent learned rules and active trusts."""
    agent = await get_agent_async()
    active = agent.broker.policy_engine.get_active_rules()
    candidates = agent.broker.policy_engine.get_candidate_rules()
    
    learned = []
    for rid, rule in active.items():
        learned.append({
            "rule_id": rid,
            "intent": rule.get("intent"),
            "pattern": rule.get("resource_pattern"),
            "effect": rule.get("effect", "allow"),
            "source": rule.get("source"),
            "description": rule.get("description"),
            "version": rule.get("version", 1),
            "created_at": rule.get("created_at")
        })
        
    pending = []
    for rid, rule in candidates.items():
        pending.append({
            "rule_id": rid,
            "intent": rule.get("intent"),
            "pattern": rule.get("resource_pattern"),
            "effect": rule.get("effect", "allow"),
            "approval_count": rule.get("approval_count", 0)
        })
        
    return {
        "active_rules": learned,
        "candidate_rules": pending
    }

@app.get("/policies")
async def get_policies():
    """Alias for trust_status with user's preferred naming."""
    agent = await get_agent_async()
    active = agent.broker.policy_engine.get_active_rules()
    candidates = agent.broker.policy_engine.get_candidate_rules()
    return {
        "active": list(active.values()),
        "candidates": list(candidates.values())
    }

@app.post("/vaults/rules/promote")
async def promote_rule(request: Request):
    """Manually promote a pattern to 'Always Allow'."""
    agent = await get_agent_async()
    data = await request.json()
    intent = data.get("intent")
    pattern = data.get("pattern")
    
    if not intent or not pattern:
        raise HTTPException(status_code=400, detail="Intent and pattern required.")
        
    result = agent.broker.promote_to_always_allow(intent, pattern)
    return result

@app.post("/vaults/rules/promote_deny")
async def promote_deny(request: Request):
    """Manually promote a pattern to 'Never Allow' (Negative Policy)."""
    agent = await get_agent_async()
    data = await request.json()
    intent = data.get("intent")
    pattern = data.get("pattern")
    
    if not intent or not pattern:
        raise HTTPException(status_code=400, detail="Intent and pattern required.")
        
    result = agent.broker.promote_to_never_allow(intent, pattern)
    return result

@app.post("/vaults/rules/simulate")
async def simulate_rule(request: Request):
    """Backtest a rule against the current episodic log."""
    agent = await get_agent_async()
    data = await request.json()
    intent = data.get("intent", "*")
    pattern = data.get("pattern")
    effect = data.get("effect", "allow")
    
    if not pattern:
        raise HTTPException(status_code=400, detail="Pattern required for simulation.")
        
    result = await asyncio.to_thread(
        agent.broker.policy_engine.simulate_policy_impact, 
        intent, pattern, effect
    )
    return result

@app.post("/policies/simulate")
async def simulate_policy_alias(request: Request):
    """User preferred endpoint for simulation."""
    agent = await get_agent_async()
    data = await request.json()
    intent = data.get("intent", "*")
    pattern = data.get("resource_pattern") # Note the difference in key name in user prompt
    effect = data.get("effect", "allow")
    
    if not pattern:
        raise HTTPException(status_code=400, detail="resource_pattern required.")
        
    result = await asyncio.to_thread(
        agent.broker.policy_engine.simulate_policy_impact,
        intent, pattern, effect
    )
    return {
        "would_affect": result.get("matches_found", 0),
        "sample_events": [] # We don't return samples yet for brevity
    }

@app.post("/policies/promote")
async def promote_policy_alias(request: Request):
    agent = await get_agent_async()
    data = await request.json()
    rule_id = data.get("rule_id")
    success = agent.broker.policy_engine.promote_rule(rule_id)
    return {"success": success}

@app.post("/policies/reject")
async def reject_policy_alias(request: Request):
    agent = await get_agent_async()
    data = await request.json()
    rule_id = data.get("rule_id")
    success = agent.broker.policy_engine.reject_rule(rule_id)
    return {"success": success}

@app.get("/vaults/rules/history/{rule_id}")
async def get_rule_history(rule_id: str):
    """Fetch the version history for a specific rule."""
    agent = await get_agent_async()
    history = agent.broker.policy_engine.get_rule_history(rule_id)
    return {"rule_id": rule_id, "history": history}

@app.post("/vaults/rules/rollback")
async def rollback_rule(request: Request):
    """Revert a rule to a specific version."""
    agent = await get_agent_async()
    data = await request.json()
    rule_id = data.get("rule_id")
    version = data.get("version")
    
    if not rule_id or not version:
        raise HTTPException(status_code=400, detail="Rule ID and version required.")
        
    success = agent.broker.policy_engine.rollback_rule(rule_id, int(version))
    return {"success": success}

@app.post("/vaults/rules/revoke")
async def revoke_rule(request: Request):
    """Remove a persistent trust rule."""
    agent = await get_agent_async()
    data = await request.json()
    rule_id = data.get("rule_id")
    
    if not rule_id:
        raise HTTPException(status_code=400, detail="Rule ID required.")
        
    success = agent.broker.policy_engine.revoke_rule(rule_id)
    return {"success": success}

@app.get("/sandbox_files")
async def get_sandbox_files():
    agent = await get_agent_async()
    try:
        files = []
        root = Path(agent.vault.sandbox)
        for item in root.rglob("*"):
            if item.is_file():
                files.append({
                    "name": item.name, 
                    "path": str(item.relative_to(root)), 
                    "size_kb": round(item.stat().st_size / 1024, 1)
                })
        return {"files": files[:100]}
    except:
        return {"files": []}

@app.get("/api/events")
async def sse_events(request: Request):
    """
    Persistent SSE stream for real-time status and Airlock notifications.
    Synchronizes state across multiple dashboard tabs.
    """
    async def event_generator():
        async for queue in event_bus.subscribe():
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break
                
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive to prevent proxy timeouts
                    yield ": keepalive\n\n"
            break

    return StreamingResponse(event_generator(), media_type="text/event-stream")
async def get_trace(trace_id: str):
    """Retrieve and decrypt a specific decision trace for forensics."""
    agent = await get_agent_async()
    try:
        # 1. Locate trace in logs
        trace_path = Path(agent.vault.vault_root) / "decision_traces.jsonl"
        if not trace_path.exists():
            raise HTTPException(status_code=404, detail="Trace log not found.")
            
        # 2. Extract specific trace entry
        trace_entry = None
        with open(trace_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line: continue
                # Traces are currently not encrypted at rest in v0.2 base, but we add decryption layer here for spec
                try:
                    # If encryption is active, decrypt the line
                    if agent.vault.key_manager and agent.vault.key_manager.is_encrypted():
                        line = agent.vault.key_manager.decrypt(line)
                    entry = json.loads(line)
                    if entry.get("trace_id") == trace_id:
                        trace_entry = entry
                        break
                except: continue
        
        if not trace_entry:
            raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found in episodic storage.")
            
        return {"success": True, "trace": trace_entry}
    except Exception as e:
        return {"success": False, "message": str(e)}

    return agent.current_trace.to_dict()

@app.get("/compliance/export")
async def export_compliance():
    """Retrieve full decrypted audit trail for compliance reporting."""
    agent = await get_agent_async()
    try:
        history = await asyncio.to_thread(agent.broker.get_audit_history, limit=1000)
        return {"success": True, "audit": history, "vault": current_vault_name}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.get("/compliance/report")
async def download_report():
    """Generate a downloadable JSON file for the audit trail."""
    agent = await get_agent_async()
    try:
        history = await asyncio.to_thread(agent.broker.get_audit_history, limit=1000)
        data = {
            "report_version": "v0.6.0-prototype",
            "vault": current_vault_name,
            "timestamp": datetime.now().isoformat(),
            "audit_trail": history
        }
        return JSONResponse(
            content=data,
            headers={"Content-Disposition": f"attachment; filename=compliance_report_{current_vault_name}.json"}
        )
    except Exception as e:
        return {"error": str(e)}

@app.get("/health")
async def health_check():
    """Basic health check for monitoring."""
    return {
        "status": "healthy",
        "version": "0.2.0-RELEASE",
        "timestamp": datetime.now().isoformat(),
        "vault_active": (current_agent is not None)
    }

@app.get("/audit/verify")
async def verify_audit_integrity():
    """Cryptographic verification of the entire audit chain."""
    agent = await get_agent_async()
    from localagent.forensics.audit_chain import AuditChainManager
    
    log_path = Path(agent.memory_service.lancedb_path).parent / "audit_log.jsonl"
    is_valid = await asyncio.to_thread(
        AuditChainManager.verify_log_integrity, 
        log_path, 
        agent.vault.key_manager
    )
    
    return {
        "success": True,
        "is_valid": is_valid,
        "log_path": str(log_path)
    }

# --- PHASE 3: REMOTE BRIDGE INGRESS ---

@app.post("/bridge/chat")
async def bridge_chat(request: Request):
    """
    Headless remote entry point with HMAC security.
    """
    # 1. Security Verification
    signature = request.headers.get("X-LocalAgent-Signature")
    timestamp = request.headers.get("X-LocalAgent-Timestamp")
    body_bytes = await request.body()
    body_str = body_bytes.decode('utf-8')
    
    if not bridge_security.verify_request(body_str, signature, timestamp):
        await apply_jitter("bridge")
        raise HTTPException(status_code=401, detail="Invalid signature or replay detected.")

    agent = await get_agent_async()
    data = json.loads(body_str)
    user_input = data.get("message")
    thought_level = data.get("thought_level", "full") # Approved tunable visibility
    
    if not user_input:
        raise HTTPException(status_code=400, detail="Message is required.")

    try:
        # Bridge is currently non-streaming for simplicity in v0.2
        response = await asyncio.to_thread(agent.chat, user_input)
        
        # Format response based on thought_level
        if isinstance(response, dict) and response.get("requires_confirmation"):
            req_id = response.get("request_id")
            pending_requests[req_id] = {
                "intent": response.get("intent"),
                "resource": response.get("resource"),
                "tool_name": response.get("tool_name"),
                "arguments": response.get("arguments"),
                "message": user_input,
                "risk_score": response.get("risk_score", 0.5)
            }
            return {
                "status": "airlock_required",
                "data": response,
                "reasoning": agent.current_trace.to_dict() if thought_level == "full" else None
            }
        
        return {
            "status": "success",
            "response": str(response),
            "reasoning": agent.current_trace.to_dict() if thought_level == "full" else None
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/bridge/confirm")
async def bridge_confirm(request: Request):
    """
    Remote confirmation for gated tools.
    """
    signature = request.headers.get("X-LocalAgent-Signature")
    timestamp = request.headers.get("X-LocalAgent-Timestamp")
    body_bytes = await request.body()
    body_str = body_bytes.decode('utf-8')
    
    if not bridge_security.verify_request(body_str, signature, timestamp):
        await apply_jitter("bridge")
        raise HTTPException(status_code=401, detail="Invalid signature or replay detected.")

    agent = await get_agent_async()
    data = json.loads(body_str)
    request_id = data.get("request_id")
    approved = data.get("approved", False)
    
    if not request_id or request_id not in pending_requests:
        await apply_jitter("bridge")
        return {"success": False, "message": "Invalid or expired request ID."}

    pending = pending_requests.pop(request_id)
    
    try:
        # Follow the same path as local confirm
        result = agent.broker.confirm_permission(pending["intent"], pending["resource"], approved)
        if not result.get("granted"):
            return {"success": False, "message": "Denied."}
            
        final_result = await asyncio.to_thread(
            agent._execute_tool, 
            pending["tool_name"], 
            pending["arguments"], 
            token=result.get("token")
        )
        return {
            "success": True,
            "response": str(final_result)
        }
    except Exception as e:
        return {"success": False, "message": str(e)}

def main():
    """CLI entry point for starting the LocalAgent Dashboard."""
    import argparse
    parser = argparse.ArgumentParser(description="Start the LocalAgent Dashboard")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--daemon-mode", action="store_true", help="Run in headless daemon mode")
    parser.add_argument("--api-token", help="Bearer token for daemon auth")
    args = parser.parse_args()
    
    # Store daemon config globally or in env
    if args.api_token:
        os.environ["LOCALAGENT_API_TOKEN"] = args.api_token
    
    if args.daemon_mode:
        print(f"Starting LocalAgent Daemon on port {args.port}...")
    
    uvicorn.run("localagent.api.app:app", host=args.host, port=args.port, reload=False)

if __name__ == "__main__":
    main()
