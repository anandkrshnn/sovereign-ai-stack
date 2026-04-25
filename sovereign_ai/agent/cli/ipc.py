from pathlib import Path

# v0.2-RELEASE uses versioned isolation and secure runtime pathing
def _get_secure_pipe_name():
    if os.name == 'nt':
        return r'\\.\pipe\localagent_v02'
    
    # Secure Unix Socket: move from world-writable /tmp to user-scoped home
    home = Path(os.getenv("LOCALAGENT_HOME", Path.home() / ".localagent"))
    run_dir = home / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    if os.name != 'nt':
        os.chmod(str(run_dir), 0o700)
    
    return str(run_dir / "localagent_v02.sock")

PIPE_NAME = _get_secure_pipe_name()

async def start_ipc_bridge():
    """
    Async wrapper for the IPC Listener. 
    Runs in the API daemon's lifespan.
    """
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _run_ipc_listener_sync)

def _run_ipc_listener_sync():
    """
    Synchronous listener loop using multiprocessing.connection.
    """
    print(f"[IPC] Listening on {PIPE_NAME}")
    try:
        # family='AF_PIPE' on Windows, 'AF_UNIX' on others
        family = 'AF_PIPE' if os.name == 'nt' else 'AF_UNIX'
        
        # Cleanup Unix socket if it exists
        if os.name != 'nt' and os.path.exists(PIPE_NAME):
            os.remove(PIPE_NAME)

        with Listener(PIPE_NAME, family=family) as listener:
            while True:
                try:
                    with listener.accept() as conn:
                        msg = conn.recv()
                        response = _handle_ipc_message(msg)
                        conn.send(response)
                except EOFError:
                    break
                except Exception as e:
                    print(f"[IPC] error: {e}")
    except Exception as e:
        print(f"[IPC] Fatal listener error: {e}")

def _handle_ipc_message(msg: Any) -> Dict[str, Any]:
    """Process commands from the CLI client."""
    if not isinstance(msg, dict):
        return {"error": "invalid_format"}

    command = msg.get("command")
    if command == "ping":
        return {"status": "ok", "version": "0.2.0-RELEASE"}
    elif command == "get_status":
        from localagent.api.app import current_agent
        return {
            "status": "online",
            "agent_loaded": current_agent is not None,
            "pid": os.getpid()
        }
    elif command == "chat":
        prompt = msg.get("params", {}).get("prompt")
        if not prompt: return {"error": "missing_prompt"}
        
        # We run the agent chat in a thread to not block the IPC listener too long
        # (Though uvicorn/asyncio handles it if we use to_thread)
        from localagent.api.app import get_agent_async
        import asyncio
        
        # Note: In a real sync IPC handler, we might have issues with nested loops.
        # We use a simplified synchronous call for v0.2
        from localagent.api.app import current_agent
        if not current_agent:
            return {"error": "agent_not_ready"}
        
        response = current_agent.chat(prompt)
        return {"status": "success", "response": response}

    elif command == "get_pending":
        from localagent.api.app import pending_requests
        return {"pending": list(pending_requests.values())}

    elif command == "confirm":
        request_id = msg.get("params", {}).get("request_id")
        choice = msg.get("params", {}).get("choice") # a, d, p, s
        
        from localagent.api.app import pending_requests, current_agent
        if request_id not in pending_requests:
            return {"error": "invalid_request_id"}
        
        pending = pending_requests.pop(request_id)
        if not current_agent:
            return {"error": "agent_not_ready"}
            
        # Apply the decision to the broker
        approved = (choice == 'a' or choice == 'p')
        result = current_agent.broker.confirm_permission(pending["intent"], pending["resource"], approved)
        
        # If approved, we can pro-actively execute the tool and return the observation, 
        # or just return success and let the user prompt again.
        # For v0.2 CLI, we'll return the result of the tool execution to the REPL.
        if approved and result.get("granted"):
            try:
                observation = current_agent._execute_tool(
                    pending["tool_name"], 
                    pending["arguments"], 
                    token=result.get("token")
                )
                return {"status": "success", "response": f"[Airlock Resolved] Observation: {observation}"}
            except Exception as e:
                return {"error": str(e)}
        
        return {"status": "success", "response": "Denial recorded."}

    elif command == "shutdown":
        # Note: Shutdown via IPC is a 'signal' to the process
        import signal
        os.kill(os.getpid(), signal.SIGTERM)
        return {"status": "shutting_down"}
    
    return {"error": "unknown_command"}

def send_ipc_command(command: str, params: Optional[Dict] = None) -> Dict[str, Any]:
    """CLI client-side utility to send commands to the daemon."""
    family = 'AF_PIPE' if os.name == 'nt' else 'AF_UNIX'
    try:
        with Client(PIPE_NAME, family=family) as conn:
            conn.send({"command": command, "params": params or {}})
            return conn.recv()
    except Exception as e:
        return {"error": "connection_failed", "detail": str(e)}
