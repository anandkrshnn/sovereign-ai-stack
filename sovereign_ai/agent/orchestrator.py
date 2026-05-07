import asyncio
import json
import uuid
import hashlib
import logging
from typing import Any, Dict, List, Optional
from functools import partial
from datetime import datetime, timezone
from cachetools import TTLCache

from .schemas import (
    AgentState, 
    IntentRecord, 
    VerificationRecord, 
    ObservationRecord, 
    RecordStatus, 
    VerifyFailSignal, 
    SecurityHalt
)
from ..common.audit import SignedAuditChain, Principal
from ..verify.evaluator import SovereignEvaluator
from .broker.engine import LocalPermissionBroker
from .idempotency import PersistentIdempotencyStore

logger = logging.getLogger(__name__)

class SovereignAgent:
    """
    The 'Fail-Closed' Sovereign AI Orchestrator.
    
    Implements the Trinity of Trust (Govern, Verify, Prove) using an 
    interceptor-based middleware chain.
    """

    def __init__(
        self, 
        broker: LocalPermissionBroker, 
        evaluator: SovereignEvaluator, 
        audit_chain: SignedAuditChain,
        idempotency_store: Optional[PersistentIdempotencyStore] = None,
        idempotency_ttl: int = 300
    ):
        self.broker = broker
        self.evaluator = evaluator
        self.audit_chain = audit_chain
        
        # Idempotency management: In-memory TTL cache + Persistent SQLite backup
        self._idempotency_cache = TTLCache(maxsize=1024, ttl=idempotency_ttl)
        self.idempotency_store = idempotency_store
        self._idempotency_lock = asyncio.Lock()

        # Phase 2: Asynchronous Forensic Logging
        self._audit_queue = asyncio.Queue()
        self._shutdown_event = asyncio.Event()
        self._audit_worker_task: Optional[asyncio.Task] = None

    def _ensure_worker_started(self):
        """Lazily start the audit worker if it's not already running."""
        if self._audit_worker_task is None:
            self._audit_worker_task = asyncio.create_task(self._audit_worker())

    async def execute_tool(
        self, 
        tool_name: str, 
        tool_args: Dict[str, Any], 
        state: AgentState, 
        context: str,
        context_version: Optional[str] = None
    ) -> Any:
        """
        Gated execution of a single tool call.
        
        Middleware Order:
        1. GOVERN (ABAC Policy Check)
        2. IDEMPOTENCY CHECK
        3. PROVE (Intent Stamp - Before)
        4. VERIFY (NLI Grounding Gate)
        5. EXECUTE & OBSERVE (PROVE Observation - After)
        """
        self._ensure_worker_started()
        state.action_id = str(uuid.uuid4())
        
        # 1. GOVERN (ABAC)
        resource = self._get_resource(tool_name, tool_args)
        perm = self.broker.request_permission(
            intent=tool_name, 
            resource=resource, 
            principal=state.principal_id,
            session_id=state.session_id,
            tool_args=tool_args
        )
        
        if not perm.get("granted"):
            await self._audit_sign("GOVERN_DENY", state, {
                "tool": tool_name,
                "resource": resource,
                "reason": perm.get("reason"),
                "rule_id": perm.get("rule_id")
            })
            raise SecurityHalt(f"Action blocked by policy: {perm.get('reason')}")

        # 2. IDEMPOTENCY CHECK
        nonce = tool_args.get("_nonce", "")
        # Contextual Idempotency: incorporate version/salt to allow re-execution on context shift
        ctx_v = context_version or "" 
        
        canonical_args = json.dumps(tool_args, sort_keys=True)
        idem_key = hashlib.sha256(
            f"{tool_name}:{resource}:{canonical_args}:{nonce}:{ctx_v}".encode()
        ).hexdigest()
        
        async with self._idempotency_lock:
            # Check in-memory first, then persistent store
            status = self._idempotency_cache.get(idem_key)
            if not status and self.idempotency_store:
                status = self.idempotency_store.get_status(idem_key)

            if status:
                if status == RecordStatus.PENDING:
                    raise SecurityHalt("Duplicate action detected (pending execution)")
                elif status == RecordStatus.SUCCESS:
                    raise SecurityHalt("Duplicate action detected (already succeeded)")
            
            self._update_idempotency(idem_key, RecordStatus.PENDING)

        # 3. PROVE (Intent - Stamp First)
        # CRITICAL: We MUST wait for the intent to be signed on-disk before 
        # proceeding to verification/execution to prevent 'Ghost Executions'.
        await self._audit_sign("agent_intent", state, {
            "action_id": state.action_id,
            "session_id": state.session_id,
            "tool_name": tool_name,
            "arguments": canonical_args,
            "abac_result": RecordStatus.ALLOW
        }, wait=True)

        # 4. VERIFY (NLI Gate)
        loop = asyncio.get_running_loop()
        v_result = await loop.run_in_executor(
            None, 
            partial(self.evaluator.evaluate, query=state.metadata.get("query", ""), context=context, answer=f"Agent wants to call {tool_name} with parameters: {canonical_args}")
        )
        
        verify_record = VerificationRecord(
            action_id=state.action_id,
            session_id=state.session_id,
            nli_score=v_result["overall_score"],
            status=RecordStatus.PASS if v_result["passed"] else RecordStatus.FAIL,
            failure_type="GROUNDING_ERROR" if not v_result["passed"] else None,
            grounding_score=v_result["grounding_score"],
            faithfulness_score=v_result["faithfulness_score"]
        )
        
        signed_v_event = await self._audit_sign("verification_gate", state, verify_record.model_dump(), wait=True)
        
        if not v_result["passed"]:
            async with self._idempotency_lock:
                self._update_idempotency(idem_key, RecordStatus.FAIL)
            
            raise VerifyFailSignal(
                failure_type=verify_record.failure_type,
                action_id=state.action_id,
                retry_count=state.retry_count,
                signed_failure_hash=signed_v_event.curr_hash
            )

        # 5. EXECUTE & OBSERVE
        start_time = datetime.now(timezone.utc)
        try:
            output = await self._dispatch_execution(tool_name, tool_args)
            
            exec_time_ms = (datetime.now(timezone.utc) - start_time).total_seconds() * 1000
            
            obs_record = ObservationRecord(
                action_id=state.action_id,
                session_id=state.session_id,
                status=RecordStatus.SUCCESS,
                output=str(output),
                execution_time_ms=exec_time_ms
            )
            await self._audit_sign("tool_observation", state, obs_record.model_dump())
            
            async with self._idempotency_lock:
                self._update_idempotency(idem_key, RecordStatus.SUCCESS)
            
            return output

        except BaseException as e:
            # SHIELD: Ensure the forensic chain closes even if cancelled
            # If the task is cancelled, shield(coro) allows coro to complete.
            try:
                await asyncio.shield(self._sign_exec_error(state, idem_key, e))
            except asyncio.CancelledError:
                # This occurs if the outer task is cancelled while awaiting the shield.
                # The inner _sign_exec_error continues running in the background.
                logger.warning(f"SHIELD_ORPHAN: Forensic write for {state.action_id} is running in background due to task cancellation.")
                raise
            raise

    def _update_idempotency(self, idem_key: str, status: RecordStatus):
        """Update both in-memory and persistent idempotency state."""
        self._idempotency_cache[idem_key] = status
        if self.idempotency_store:
            self.idempotency_store.set_status(idem_key, status)

    async def _audit_sign(self, action: str, state: AgentState, data: Dict[str, Any], wait: bool = False) -> Optional[Any]:
        """Queue an audit record for background signing."""
        self._ensure_worker_started()
        loop = asyncio.get_running_loop()
        future = loop.create_future() if wait else None
        
        payload = {
            "action": action,
            "principal": state.principal_id,
            "event_data": data,
            "future": future
        }
        await self._audit_queue.put(payload)
        
        if wait and future:
            return await future
        return None

    async def _audit_worker(self):
        """Background worker that processes and signs audit events."""
        logger.info("Audit worker started.")
        while not self._shutdown_event.is_set() or not self._audit_queue.empty():
            try:
                # Wait for an item or a shutdown signal
                try:
                    # If shutting down, don't wait for a second, just process what's left
                    timeout = 1.0 if not self._shutdown_event.is_set() else 0.1
                    payload = await asyncio.wait_for(self._audit_queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    continue

                # Process event: SignedAuditChain.log_event is synchronous
                loop = asyncio.get_running_loop()
                event = await loop.run_in_executor(
                    None,
                    partial(
                        self.audit_chain.log_event,
                        component="orchestrator",
                        action=payload["action"],
                        principal=payload["principal"],
                        event_data=payload["event_data"]
                    )
                )
                
                # If a future was provided, set the result
                future = payload.get("future")
                if future and not future.done():
                    future.set_result(event)
                    
                self._audit_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audit worker error: {e}")
                # Ensure future is resolved even on error
                future = payload.get("future") if 'payload' in locals() else None
                if future and not future.done():
                    future.set_exception(e)
                    
        logger.info("Audit worker stopped.")

    async def close(self):
        """Gracefully shutdown the orchestrator and drain the audit queue."""
        self._shutdown_event.set()
        if self._audit_worker_task:
            await self._audit_worker_task

    async def _sign_exec_error(self, state: AgentState, idem_key: str, error: Exception):
        """Internal helper for cancellation-safe error logging."""
        await self._audit_sign("tool_observation", state, ObservationRecord(
            action_id=state.action_id,
            session_id=state.session_id,
            status=RecordStatus.EXEC_ERROR,
            error=str(error)
        ).model_dump())
        
        async with self._idempotency_lock:
            self._update_idempotency(idem_key, RecordStatus.EXEC_ERROR)

    async def _dispatch_execution(self, name: str, args: Dict[str, Any]) -> Any:
        """
        Dispatches the tool call to the actual implementation.
        In the Sovereign Stack, this maps to the sandbox-aware tool handlers.
        """
        # Placeholder: Real implementation would look up the tool in a registry.
        logger.info(f"Executing tool {name} with args {args}")
        # Simulation for demonstration:
        await asyncio.sleep(0.01) 
        return f"Simulated output for {name}"

    def _get_resource(self, name: str, args: Dict[str, Any]) -> str:
        """Robustly extract the primary resource (e.g. path) from tool arguments."""
        norm_args = {k.lower(): v for k, v in args.items()}
        for key in ["path", "filename", "file", "target", "resource", "directory", "folder", "query", "key", "text"]:
            if key in norm_args and norm_args[key]:
                return str(norm_args[key])
        return "unknown"
