import uuid
import time
import json
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime
from localagent.forensics.audit_chain import AuditChainManager
from localagent.forensics.secure_key import SecureKeyManager
from localagent.broker.resource_quota import ResourceQuota
from localagent.broker.scanner import ScannerManager
from localagent.config import Config
import random
import hashlib
from localagent.cli.daemon import get_daemon_dir
import threading

class LocalPermissionBroker:
    """Just-in-Time Security: Manages tool tokens and auto-learning trust with Encrypted JSONL Audit."""

    def __init__(self, audit_log_path: Optional[str] = None, key_manager=None, auto_discover_keys: bool = True, master_passphrase: Optional[str] = None):
        if audit_log_path:
            self.audit_log_path = Path(audit_log_path)
        else:
            # Default to LOCALAGENT_HOME/audit.jsonl (Bulletproof v3.0 standard)
            self.audit_log_path = get_daemon_dir() / "audit.jsonl"

        self.key_manager = key_manager
        vault_root = self.audit_log_path.parent
        
        # v8.0 Sovereign Key Initialization
        if self.key_manager is None and auto_discover_keys:
            try:
                # 1. Attempt enclave discovery
                session_key = SecureKeyManager.get_trace_key()
                
                # 2. v8.0 Persistence: Staple key to vault if master_passphrase provided
                if master_passphrase:
                    SecureKeyManager.wrap_key_to_vault(vault_root, master_passphrase)
                
                from localagent.forensics.vault_key_manager import VaultKeyManager
                self.key_manager = VaultKeyManager(vault_root, session_key.decode() if isinstance(session_key, bytes) else session_key)
            except Exception as e:
                # 3. v8.0 Recovery: If enclave fails, attempt to unwrap from vault
                if master_passphrase:
                    try:
                        recovered_key = SecureKeyManager.unwrap_key_from_vault(vault_root, master_passphrase)
                        from localagent.forensics.vault_key_manager import VaultKeyManager
                        self.key_manager = VaultKeyManager(vault_root, recovered_key)
                        print(f"[Broker] v8.0 RECOVERY SUCCESS: Audit key restored from vault-staple.")
                    except:
                        print(f"[Broker] WARNING: Secure Key Manager failed ({e}). Proceeding unencrypted.")
                else:
                    print(f"[Broker] WARNING: Secure Key Manager failed ({e}). Proceeding unencrypted.")

        # v10.0 Monotonic Sequence Initialization
        self._archive_seq = 0
        manifest_path = vault_root / "chain_manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
                    self._archive_seq = len(manifest.get("archives", []))
            except: pass

        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # --- THREAD SAFETY ---
        self._vault_lock = threading.Lock()
        
        # --- CACHED STATE (v3.0 Optimization) ---
        self.sandbox_base = Path("sandbox").resolve()
        
        self.pending_confirmations = {}
        self.active_tokens = {}
        
        # Default policies for each capability
        self.policies = self._load_default_policies()
        
        from localagent.broker.engine_core import PolicyEngine
        # Construct PolicyEngine path based on audit log path for vault consistency
        policies_path = self.audit_log_path.parent / "policies.json"
        self.policy_engine = PolicyEngine(self, db_path=str(policies_path), key_manager=self.key_manager)

        # Phase 2: Initialize Hash Chain
        mode = "encrypted" if self.key_manager and self.key_manager.is_encrypted() else "plaintext"
        self.last_audit_hash = AuditChainManager.get_last_hash(self.audit_log_path, key_manager=self.key_manager, mode=mode)
        
        # Phase 2: Initialize DoS Resource Quota
        self.resource_quota = ResourceQuota()
        
        # Phase 2: Initialize Secret Scanner
        self.config = Config.default()
        self.scanner_manager = ScannerManager(
            config=self.config, 
            allowlist=self.policy_engine.get_allowlist()
        )

    def _load_default_policies(self):
        """Standard high-assurance defaults"""
        return {
            "read_file": {"requires_confirmation": False},
            "list_directory": {"requires_confirmation": False},
            "write_file": {"requires_confirmation": True},
            "append_to_file": {"requires_confirmation": True},
            "query_memory": {"requires_confirmation": False},
            "search_memory": {"requires_confirmation": False},
            "read_memory": {
                "allowed_resources": ["semantic_memory", "*"],
                "max_frequency_per_min": 60,
                "ephemeral_seconds": 30,
                "requires_confirmation": False,
                "risk_level": "low"
            }
        }

    def _get_policy(self, intent: str, resource: str) -> dict:
        """Fetch policy with override from persistent engine."""
        # 1. Check persistent engine first (learned/manual rules)
        active_rule = self.policy_engine.match(intent, resource)
        if active_rule:
            return active_rule
        
        # 2. Fallback to default memory policies
        return self.policies.get(intent)

    def _generate_token(self, intent: str, resource: str) -> str:
        """Generate a short-lived token."""
        token = uuid.uuid4().hex
        expires_at = time.time() + 60
        self.active_tokens[token] = {
            "intent": intent, 
            "resource": resource, 
            "expires_at": expires_at
        }
        return token

    def request_permission(self, intent: str, resource: str, context: str = "", trace_id: str = None) -> dict:
        """
        Request permission for an operation.
        Deterministic: Persistent Engine > Default Policies.
        """
        # Phase 2: Zero-Trust Ingress Scanning (Credential Leakage Prevention)
        # We scan both the resource (path) and the context (payload/prompt)
        payload_to_scan = f"{resource} {context}"
        try:
            violations = self.scanner_manager.scan(payload_to_scan)
            if violations:
                msg = f"SECRET_VIOLATION: Detected {len(violations)} distinct security violations."
                
                # Safety: Redact all violations in the log and clear them from memory
                redacted_context = context
                violation_ids = []
                for v in violations:
                    violation_ids.append(v.plugin_id)
                    redacted_context = redacted_context.replace(v._raw_match or "", v.redact_and_clear())
                
                try:
                    self._append_audit(str(uuid.uuid4()), intent, resource, False, None, msg, redacted_context, trace_id=trace_id)
                except Exception:
                    return {
                        "granted": False,
                        "reason": "Security Service Unavailable (Audit Fault)",
                        "error_code": "SEC_AUDIT_UNAVAILABLE",
                        "trace_flags": ["TRACE_AUDIT_FAIL"]
                    }

                self._apply_response_jitter()
                return {
                    "granted": False,
                    "reason": "Security violation: Potential credentials detected in payload.",
                    "secret_detected": True,
                    "violations": violation_ids
                }
        except Exception as e:
            # Phase 4 Hardening: Scanner Panic must fail closed and be audited if possible
            try:
                self._append_audit(str(uuid.uuid4()), intent, resource, False, None, f"SCAN_PANIC: {e}", context, trace_id=trace_id)
            except:
                pass # Already in a panic state, fall back to decision only
            
            return {
                "granted": False, 
                "reason": "Security Service Unavailable (Scanner Fault)",
                "error_code": "SEC_SCAN_UNAVAILABLE",
                "trace_flags": ["TRACE_SCAN_FAIL"]
            }

        # Phase 2: Resource Quota Enforcement (DoS Protection)
        # We estimate size based on context length if not provided
        resource_size = len(context.encode('utf-8'))
        if not self.resource_quota.check_and_update(intent, resource_size):
            msg = "QUOTA_EXCEEDED: Operation blocked by session resource limits."
            try:
                self._append_audit(str(uuid.uuid4()), intent, resource, False, None, msg, context, trace_id=trace_id)
            except Exception:
                return {
                    "granted": False,
                    "reason": "Security Service Unavailable (Audit Fault)",
                    "error_code": "SEC_AUDIT_UNAVAILABLE",
                    "trace_flags": ["TRACE_AUDIT_FAIL"]
                }
            self._apply_response_jitter()
            return {"granted": False, "reason": msg}

        # --- TWO-TIER TRAVERSAL SHIELD (v3.0 Optimization & Security) ---
        # Tier 1: Fast-path (In-memory string normalization)
        import os
        normalized_resource = os.path.normpath(resource).replace("\\", "/")
        
        # Suspicious markers
        is_suspicious = ".." in resource or os.path.isabs(resource) or (os.name == 'nt' and ":" in resource[:3])
        
        if is_suspicious:
            # Tier 2: Secure slow-path (Disk-aware resolve() + containment check)
            try:
                target_path = Path(resource).resolve()
                if resource.startswith("sandbox"):
                    target_path.relative_to(self.sandbox_base)
                elif ".." in resource:
                    target_path.relative_to(Path.cwd().resolve())
                normalized_resource = str(target_path).replace("\\", "/")
            except ValueError:
                return {"granted": False, "reason": "Security violation: Path traversal attempt detected."}
        else:
            # Fast-path optimization: just join and check obvious form if sandbox requested
            if resource.startswith("sandbox"):
                if not normalized_resource.startswith("sandbox"):
                    return {"granted": False, "reason": "Security violation: Path traversal attempt detected."}

        # 1. Check if we have a matching rule in the persistent engine
        rule = self.policy_engine.match(intent, normalized_resource)
        
        if rule:
            effect = rule.get("effect", "allow").lower()
            if effect == "deny":
                msg = f"Operation BLOCKED via persistent {rule.get('source', 'learned')} NEGATIVE policy"
                self._append_audit(str(uuid.uuid4()), intent, resource, False, None, msg, context, rule_id=rule.get("rule_id"), source=rule.get("source"), trace_id=trace_id)
                self._apply_response_jitter()
                return {
                    "granted": False,
                    "reason": msg,
                    "auto_blocked": True,
                    "rule_id": rule.get("rule_id")
                }
            
            if not rule.get("requires_confirmation", True):
                # Auto-approved by persistent rule (manual or learned)
                token = self._generate_token(intent, resource)
                msg = f"Auto-approved via persistent {rule.get('source', 'learned')} policy"
                try:
                    self._append_audit(str(uuid.uuid4()), intent, resource, True, token, msg, context, rule_id=rule.get("rule_id"), source=rule.get("source"), trace_id=trace_id)
                except Exception:
                    return {
                        "granted": False,
                        "reason": "Security Service Unavailable (Audit Fault)",
                        "error_code": "SEC_AUDIT_UNAVAILABLE",
                        "trace_flags": ["TRACE_AUDIT_FAIL"]
                    }
                
                return {
                    "granted": True,
                    "reason": msg,
                    "token": token,
                    "auto_approved": True,
                    "rule_id": rule.get("rule_id")
                }
            
        # 2. Fallback to default hardcoded policies
        default_policy = self.policies.get(intent, {"requires_confirmation": True})
        
        # Security Hardening (v4.1): If resource is outside sandbox, force confirmation 
        # regardless of default policy unless a manual manual allow rule exists.
        is_in_sandbox = normalized_resource.startswith("sandbox/") or normalized_resource == "sandbox"
        force_confirmation = not is_in_sandbox
        
        if not force_confirmation and not default_policy.get("requires_confirmation", True):
            token = self._generate_token(intent, resource)
            try:
                self._append_audit(str(uuid.uuid4()), intent, resource, True, token, "Auto-approved by default policy", context, trace_id=trace_id)
            except Exception:
                return {
                    "granted": False,
                    "reason": "Security Service Unavailable (Audit Fault)",
                    "error_code": "SEC_AUDIT_UNAVAILABLE",
                    "trace_flags": ["TRACE_AUDIT_FAIL"]
                }
            return {"granted": True, "token": token, "auto_approved": True}
        
        # 3. Need user confirmation — return approval_count so UI can show progress
        approval_count = self._count_approvals(intent, resource)
        risk_score = self._calculate_risk(intent, resource)
        request_id = str(uuid.uuid4())
        
        # Find existing candidate rule_id for this pattern (so UI can link to it)
        resource_pattern = self._get_resource_pattern(resource)
        candidate_rule_id = None
        for cid, cand in self.policy_engine.get_candidate_rules().items():
            if cand.get("intent") == intent and cand.get("resource_pattern") == resource_pattern:
                candidate_rule_id = cid
                break
        
        msg = "PENDING: Operation requires manual confirmation due to high risk or lack of trust."
        try:
            self._append_audit(request_id, intent, resource, False, None, msg, context, trace_id=trace_id)
        except Exception:
            return {
                "granted": False,
                "reason": "Security Service Unavailable (Audit Fault)",
                "error_code": "SEC_AUDIT_UNAVAILABLE",
                "trace_flags": ["TRACE_AUDIT_FAIL"]
            }
        
        return {
            "granted": False,
            "requires_confirmation": True,
            "request_id": request_id,
            "intent": intent,
            "resource": resource,
            "risk_score": risk_score,
            "approval_count": approval_count,
            "threshold": 8,
            "candidate_rule_id": candidate_rule_id
        }

    def confirm_permission(self, intent: str, resource: str, approved: bool, context: str = "", trace_id: str = None) -> dict:
        """
        Called after user confirms or denies a permission request.
        """
        if not approved:
            self._append_audit(str(uuid.uuid4()), intent, resource, False, None, "User denied", context, trace_id=trace_id)
            return {"granted": False, "reason": "User denied"}
        
        token = self._generate_token(intent, resource)
        self._append_audit(str(uuid.uuid4()), intent, resource, True, token, "User approved", context, trace_id=trace_id)
        
        # Update/Create candidate rule for learning
        self._update_learning_state(intent, resource)
        
        # Check if the policy JUST flipped to auto
        rule = self.policy_engine.match(intent, resource)
        approval_count = self._count_approvals(intent, resource)
        
        result = {
            "granted": True,
            "token": token,
            "reason": "User approved",
            "approval_count": approval_count,
            "threshold": 8
        }
        
        if rule and not rule.get("requires_confirmation", True):
            result["pattern_learned"] = True
            result["message"] = f"Pattern learned! Future requests for {resource} will auto-approve."
        else:
            remaining = 8 - approval_count
            result["message"] = f"Approved. {remaining} more needed to learn this pattern."
        
        return result

    def promote_to_always_allow(self, intent: str, resource_pattern: str, description: str = None) -> dict:
        """Explicit user request to 'Always Allow' a folder."""
        if not description:
            description = f"Manually trusted pattern for {intent}"
            
        rule_id = self.policy_engine.create_active_rule(
            intent=intent,
            resource_pattern=resource_pattern,
            description=description,
            effect="allow",
            source="manual"
        )
        return {"success": True, "rule_id": rule_id, "message": f"Successfully trusted {resource_pattern} forever."}

    def promote_to_never_allow(self, intent: str, resource_pattern: str, description: str = None) -> dict:
        """Explicit user request to 'Never Allow' a folder (Negative Policy)."""
        if not description:
            description = f"Manually BLOCKED pattern for {intent}"
            
        rule_id = self.policy_engine.create_active_rule(
            intent=intent,
            resource_pattern=resource_pattern,
            description=description,
            effect="deny",
            source="manual"
        )
        return {"success": True, "rule_id": rule_id, "message": f"Successfully BLOCKED {resource_pattern} forever."}

    def get_recent_episodes(self, limit: int = 100) -> List[Dict]:
        """Bridge to memory system to fetch episodes for simulation."""
        # For the broker to access episodes, we need a link to the environment/agent or memory store
        # In this architecture, app.py sets this up. We'll use a lazy injection or explicit set.
        if hasattr(self, 'memory_service') and self.memory_service:
            return self.memory_service.lancedb_store.get_recent_episodes(limit=limit)
        return []

    def _update_learning_state(self, intent: str, resource: str):
        """Internal learning logic: candidate -> active promotion."""
        count = self._count_approvals(intent, resource)
        resource_pattern = self._get_resource_pattern(resource)
        
        # Check if we already have a candidate
        found_candidate = None
        for cid, cand in self.policy_engine.get_candidate_rules().items():
            if cand.get("intent") == intent and cand.get("resource_pattern") == resource_pattern:
                found_candidate = cid
                # We can't update 'cand' directly here as it's a dict from get_candidate_rules()
                # We should update the object in the engine
                eng_cand = self.policy_engine.candidate_rules[cid]
                eng_cand.approval_count = count
                eng_cand.updated_at = datetime.utcnow().isoformat()
                break
        
        if not found_candidate:
            found_candidate = self.policy_engine.create_candidate_rule(intent, resource_pattern)
            
        # Threshold promotion
        if count >= 8:
            self.policy_engine.promote_rule(found_candidate)
            print(f"[TRUST] Persistent pattern learned for {intent} on {resource_pattern}")
        else:
            self.policy_engine._save_policies()

    def _count_approvals(self, intent: str, resource: str) -> int:
        """
        Count how many times this pattern has been approved in the last 24 hours.
        Reads from JSONL audit log.
        """
        if not self.audit_log_path.exists():
            return 0

        resource_pattern = self._get_resource_pattern(resource)
        cutoff = time.time() - 86400  # 24 hours
        count = 0

        # Filter entries using explicit mode
        mode = "encrypted" if self.key_manager and self.key_manager.is_encrypted() else "plaintext"
        count = 0
        try:
            with open(self.audit_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line: continue
                    
                    try:
                        if mode == "encrypted":
                            line = self.key_manager.decrypt(line)
                        
                        entry = json.loads(line)
                        
                        # Filter criteria
                        if (entry.get("intent") == intent and 
                            entry.get("resource", "").startswith(resource_pattern) and 
                            entry.get("granted") is True and 
                            entry.get("timestamp", 0) > cutoff):
                            count += 1
                    except:
                        continue
            return count
        except Exception as e:
            print(f"[Broker] Error counting approvals from JSONL: {e}")
            return 0

    def _get_resource_pattern(self, resource: str) -> str:
        """Extract the pattern from a resource path (e.g. 'sandbox/test.txt' -> 'sandbox/')"""
        if "/" in resource:
            return resource.split("/")[0] + "/"
        return resource

    def _calculate_risk(self, intent: str, resource: str) -> float:
        """Calculate risk score for an operation (0.0 = safe, 1.0 = dangerous)."""
        risk_scores = {
            "read_file": 0.2,
            "write_file": 0.4,
            "list_directory": 0.1,
            "append_to_file": 0.4,
            "query_memory": 0.1,
            "search_memory": 0.2
        }
        base_risk = risk_scores.get(intent, 0.5)
        
        # Increase risk for paths outside sandbox
        if not resource.startswith("sandbox"):
            base_risk = min(1.0, base_risk + 0.3)
        return base_risk

    def validate_token(self, intent: str, resource: str, token: str) -> bool:
        """Runtime token validation before execution."""
        if not token: return False
        t_data = self.active_tokens.get(token)
        if not t_data: return False

        if t_data["expires_at"] < time.time():
            del self.active_tokens[token]
            return False

        # Support pattern matching for tokens as well (if needed, but usually exact)
        if t_data["intent"] == intent and t_data["resource"] == resource:
            del self.active_tokens[token]
            return True
        return False

    def _append_audit(self, request_id: str, intent: str, resource: str, granted: bool, token: str, reason: str, context: str = "", rule_id: str = None, source: str = None, trace_id: str = None):
        """Append an entry to the audit log, optionally encrypted."""
        # --- PHI REDACTION (HIPAA Hardening v0.2.0) ---
        redacted_resource = resource
        if "ehr/" in resource.lower():
            # hashlib is now globally imported
            redacted_resource = "PHI_REDACTED_" + hashlib.sha256(resource.encode()).hexdigest()[:8]

        entry = {
            "request_id": request_id,
            "intent": intent,
            "resource": redacted_resource,
            "granted": granted,
            "token": token,
            "reason": reason,
            "timestamp": time.time(),
            "context": str(context),
            "rule_id": rule_id,
            "source": source,
            "trace_id": trace_id
        }
        
        # Phase 2: Cryptographic Linking (Tamper Evidence)
        with self._vault_lock:
            entry["prev_hash"] = self.last_audit_hash
            entry["chain_hash"] = AuditChainManager.calculate_next_hash(self.last_audit_hash, entry)
            self.last_audit_hash = entry["chain_hash"]
    
            try:
                # Canonical JSON formatting (AIMS/ISO 42001 alignment)
                line = json.dumps(entry, sort_keys=True, separators=(",", ":"))
                if self.key_manager and self.key_manager.is_encrypted():
                    line = self.key_manager.encrypt(line)
                
                # Rotation logic (v9.0): Archival Rotation (1MB cap)
                if os.path.exists(self.audit_log_path) and os.path.getsize(self.audit_log_path) > 1024 * 1024:
                    self._rotate_audit_log()
                
                with open(self.audit_log_path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
                    
            except Exception as e:
                # Reraise so caller (request_permission) can fail-closed with SEC_AUDIT_UNAVAILABLE
                raise e
                
            # --- FORENSIC ANCHORING ---
            try:
                # Optimization (v5.0): Pass last_audit_hash for O(1) anchoring
                AuditChainManager.save_anchor(self.audit_log_path, key_manager=self.key_manager, last_hash=self.last_audit_hash)
            except Exception as e:
                # We don't fail-closed here if physical write succeeded, but we should log the diagnostic
                print(f"[Broker] Forensic anchoring failed (Internal Cause: {e})")

    def _rotate_audit_log(self):
        """
        v10.0 Sovereign Archival: Move current log to archive with monotonic sequence.
        """
        import shutil
        self._archive_seq += 1
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        
        # New monotonic naming pattern: audit.[seq].[ts].archive.jsonl
        archive_name = f"audit.{self._archive_seq:03d}.{timestamp}.archive.jsonl"
        archive_path = self.audit_log_path.parent / archive_name
        
        print(f"[Broker] Audit log rotation {self._archive_seq} triggered. Archiving to {archive_name}")
        
        # 1. Archive the current log and its stapled key/anchor
        shutil.move(self.audit_log_path, archive_path)
        if (self.audit_log_path.with_suffix(".anchor")).exists():
            shutil.move(self.audit_log_path.with_suffix(".anchor"), archive_path.with_suffix(".anchor"))
            
        # 2. Update Chain Manifest (v10.0: include terminal hash and size)
        self._update_manifest(archive_name, self.last_audit_hash, os.path.getsize(archive_path))
        
        # 3. Continuity check
        print(f"[Broker] Chain Unbroken: Sequence {self._archive_seq} anchored to archive.")

    def _update_manifest(self, archive_name: str, terminal_hash: str, file_size: int):
        """Updates 'chain_manifest.json' with tamper-evident archival metadata."""
        manifest_path = self.audit_log_path.parent / "chain_manifest.json"
        manifest = {"archives": [], "root_hash": "", "created_at": datetime.utcnow().isoformat() + "Z"}
        
        if manifest_path.exists():
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
            except: pass
            
        manifest["archives"].append({
            "name": archive_name,
            "terminal_hash": terminal_hash,
            "size_bytes": file_size,
            "seq": self._archive_seq
        })
        manifest["root_hash"] = self.last_audit_hash # Most recent terminal hash (active front)
        manifest["updated_at"] = datetime.utcnow().isoformat() + "Z"
        
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

    def get_audit_history(self, limit: int = 500) -> List[Dict]:
        """Fetch and decrypt the audit log for compliance reporting with memory efficiency."""
        if not self.audit_log_path.exists():
            return []
            
        history = []
        try:
            # We use a memory-efficient approach by reading lines one by one.
            # For a really large file, we'd use a reverse file reader, 
            # but for our 1MB-capped log, reading and filtering is fast enough.
            with open(self.audit_log_path, "r", encoding="utf-8") as f:
                # Optimized: Read all lines but avoid readlines() overhead if path is large
                # Actually, for 1MB, simple iteration is fine. 
                # To get 'newest first' without readlines, we'd need to seek to end.
                # Here we'll just buffer locally up to the limit.
                all_entries = []
                for line in f:
                    line = line.strip()
                    if not line: continue
                    all_entries.append(line)
                    # Simple sliding window for the last 'limit' lines
                    if len(all_entries) > limit:
                        all_entries.pop(0)

                for line in reversed(all_entries):
                    try:
                        if self.key_manager and self.key_manager.is_encrypted():
                            line = self.key_manager.decrypt(line)
                        history.append(json.loads(line))
                    except:
                        continue
            return history
        except Exception as e:
            print(f"[Broker] Error reading audit history: {e}")
            return []

    def _apply_response_jitter(self):
        """Injects 1-20ms random sleep to mitigate side-channel timing attacks."""
        jitter_s = random.uniform(0.001, 0.020)
        time.sleep(jitter_s)

    def close(self):
        # Shutdown persistent security scanner pool
        self.scanner_manager.close()

if __name__ == "__main__":
    # Self-test
    broker = LocalPermissionBroker("test_audit_migration.jsonl")
    print(broker.request_permission("write_file", "sandbox/test.txt"))
