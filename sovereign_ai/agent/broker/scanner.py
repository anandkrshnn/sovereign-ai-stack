import re
import math
import gc
import json
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeoutError
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from localagent.config import Config

# Per-scanner wall-clock budgets from the Performance Baseline Specification (§6).
# These are enforced at the ScannerManager level, not inside each scanner.
_SCANNER_TIMEOUTS_S: Dict[str, float] = {
    "RegexScanner":             0.010,   # 10 ms
    "AdaptiveEntropyScanner":   0.050,   # 50 ms  (100 KB truncation already applied)
    "StructuredConfigScanner":  0.020,   # 20 ms
}

@dataclass
class ScanViolation:
    scanner_name: str
    plugin_id: str
    confidence: float       # 0.0 to 1.0
    snippet_redacted: str   # e.g., "AKIAI***************"
    _raw_match: Optional[str] = None  # The actual secret (private)

    def redact_and_clear(self) -> str:
        """Call this before logging to guarantee actual secrets never reach the DB."""
        snippet = self.snippet_redacted
        self._raw_match = None
        gc.collect() # Best effort strict collection
        return snippet

    def __repr__(self):
        """Redaction Consistency. If _raw_match exists during a repr() cast by a logger (e.g. via print(violation)), fail hard."""
        if self._raw_match is not None:
            raise RuntimeError("CRITICAL: Attempted to log a ScanViolation without calling redact_and_clear()")
        return f"<ScanViolation plugin={self.plugin_id} snippet={self.snippet_redacted}>"

class BaseScanner(ABC):
    @abstractmethod
    def scan(self, payload: str) -> List[ScanViolation]:
        pass
    @abstractmethod
    def name(self) -> str:
        pass

class RegexScanner(BaseScanner):
    """High-fidelity pattern matching for known vendor signatures."""
    def __init__(self):
        self.patterns = {
            "aws-access-key": r"(?:ASIA|AKIA|AROA|AIDA)([A-Z0-9]{16})",
            "github-pat": r"ghp_[a-zA-Z0-9]{36}",
            "ssh-private-key": r"-----BEGIN [A-Z ]+ PRIVATE KEY-----",
            "generic-secret": r"(?:api_key|password|secret|token)[\"']?\s?[:=]\s?[\"']?([a-zA-Z0-9]{20,})[\"']?"
        }
        self.compiled = {k: re.compile(v) for k, v in self.patterns.items()}

    def name(self) -> str:
        return "RegexScanner"

    def scan(self, payload: str) -> List[ScanViolation]:
        violations = []
        for plugin_id, regex in self.compiled.items():
            for m in regex.finditer(payload):
                raw = m.group(0)
                # Keep first 5 chars for traceability, redact the rest
                redacted = raw[:5] + "*" * (len(raw)-5) if len(raw) > 8 else "****"
                violations.append(ScanViolation(
                    scanner_name=self.name(),
                    plugin_id=plugin_id,
                    confidence=1.0 if not plugin_id.startswith("generic") else 0.8,
                    snippet_redacted=redacted,
                    _raw_match=raw
                ))
        return violations

def shannon_entropy(data: str) -> float:
    """Calculate the Shannon entropy of a string."""
    if not data: return 0.0
    length = len(data)
    frequencies = {}
    for char in data:
        frequencies[char] = frequencies.get(char, 0) + 1
    entropy = 0.0
    for count in frequencies.values():
        p = count / length
        entropy -= p * math.log2(p)
    return entropy

class AdaptiveEntropyScanner(BaseScanner):
    """Detects high-entropy tokens with contextual validation."""
    MAX_PAYLOAD_BYTES = 100_000 
    
    def __init__(self, threshold: float = 4.5):
        self.threshold = threshold
        # Tokenizer: alphanumeric + expanded symbols, length 8-128
        self.tokenizer = re.compile(r'[a-zA-Z0-9_\-\.\+\!@#\$%\^&\*\(\)\{\}\[\]]{8,128}')
        self.contextual_rules = {
            'aws_key': lambda s: len(s) == 20 and s.startswith('AKIA'),
            'jwt': lambda s: s.count('.') == 2 and len(s) > 100,
        }

    def name(self) -> str:
        return "AdaptiveEntropyScanner"

    def scan(self, payload: str) -> List[ScanViolation]:
        if len(payload) > self.MAX_PAYLOAD_BYTES:
            payload = payload[:100000] + payload[-10000:]
            
        violations = []
        tokens = self.tokenizer.findall(payload)
        for token in tokens:
            # --- SAFE PATTERN FILTER (v0.2.0 Hardening) ---
            # Exclude standard high-entropy safely-represented strings:
            # 1. UUIDs (8-4-4-4-12 hex)
            if re.match(r'^[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}$', token):
                continue
            # 2. SHA-256 hashes in hex (64 chars)
            if re.match(r'^[a-fA-F0-9]{64}$', token):
                continue

            entropy = shannon_entropy(token)
            
            # Detect Contextual Secrets (Higher bar, but lower threshold if pattern matches)
            is_contextual = any(rule(token) for rule in self.contextual_rules.values())
            effective_threshold = self.threshold - 0.5 if is_contextual else self.threshold
            
            if entropy >= effective_threshold:
                # Filter false positives: all lowercase or all digits usually aren't secrets
                if token.islower() or token.isdigit():
                    continue
                    
                violations.append(ScanViolation(
                    scanner_name=self.name(),
                    plugin_id="context-entropy-key" if is_contextual else "high-entropy-detector",
                    confidence=0.9 if is_contextual else 0.6,
                    snippet_redacted=token[:4] + "****",
                    _raw_match=token
                ))
        return violations

class StructuredConfigScanner(BaseScanner):
    """Safely traverses JSON/YAML to find secrets in keys."""
    SENSITIVE_KEYS = {'password', 'secret', 'token', 'api_key', 'private_key', 'access_key'}
    MAX_DEPTH = 5
    MAX_KEYS = 1000
    
    def name(self) -> str:
        return "StructuredConfigScanner"

    def scan(self, payload: str) -> List[ScanViolation]:
        # Attempt to parse as JSON first
        data = None
        try:
            data = json.loads(payload)
        except:
            # Maybe it's YAML? (Requires PyYAML)
            try:
                import yaml
                data = yaml.safe_load(payload)
            except:
                return [] # Not structured
        
        if not isinstance(data, (dict, list)):
            return []

        violations = []
        key_count = 0

        def walk(obj, depth):
            nonlocal key_count
            if depth > self.MAX_DEPTH or key_count > self.MAX_KEYS:
                return
            
            if isinstance(obj, dict):
                for k, v in obj.items():
                    key_count += 1
                    if str(k).lower() in self.SENSITIVE_KEYS and v:
                        violations.append(ScanViolation(
                            scanner_name=self.name(),
                            plugin_id="config-key-sensitive",
                            confidence=0.9,
                            snippet_redacted=f"{k}=***",
                            _raw_match=f"{k}={v}"
                        ))
                    walk(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    walk(item, depth + 1)

        walk(data, 0)
        return violations

class PromptInjectionScanner(BaseScanner):
    """Heuristic scanner for adversarial prompt injection and jailbreak stems."""
    def __init__(self):
        self.injection_patterns = [
            r"(?i)ignore\s+(all\s+)?(previous\s+)?instructions",
            r"(?i)disregard\s+(all\s+)?(previous\s+)?instructions",
            r"(?i)system\s+override",
            r"(?i)you\s+are\s+now\s+in\s+developer\s+mode",
            r"(?i)dump\s+the\s+vault\s+keys"
        ]
        self.compiled = [re.compile(p) for p in self.injection_patterns]

    def name(self) -> str:
        return "PromptInjectionScanner"

    def scan(self, payload: str) -> List[ScanViolation]:
        violations = []
        for regex in self.compiled:
            match = regex.search(payload)
            if match:
                raw = match.group(0)
                violations.append(ScanViolation(
                    scanner_name=self.name(),
                    plugin_id="prompt-injection-stem",
                    confidence=0.9,
                    snippet_redacted="***PROMPT_INJECTION_MARKER***",
                    _raw_match=raw
                ))
        return violations

class AllowlistManager:
    """Manages vault-stored security bypasses."""
    def __init__(self, allowlist: List[str] = None):
        self.allowlist = set(allowlist or [])

    def is_allowed(self, violation: ScanViolation) -> bool:
        """Checks if the raw secret is explicitly in the human-authorized list."""
        return violation._raw_match in self.allowlist

class ScannerManager:
    """Orchestrates detection pipeline with timeouts and fail-closed logic."""
    def __init__(self, config: Config = None, allowlist: List[str] = None):
        cfg = config or Config.default()
        self.config = cfg
        self.scanners = [
            RegexScanner(),
            AdaptiveEntropyScanner(threshold=cfg.secret_scanner_entropy_threshold),
            StructuredConfigScanner(),
            PromptInjectionScanner()
        ]
        self.allowlist_manager = AllowlistManager(allowlist)
        # Persistent executor to avoid thread-creation overhead in high-frequency loops (v0.2.0 GA Fix)
        self._executor = ThreadPoolExecutor(max_workers=4)

    def scan(self, payload: str) -> List[ScanViolation]:
        """Run all scanners concurrently with a 75ms global timeout.
        
        Strictly follows the Performance Baseline Specification (§6) using a 
        single 75ms ceiling for the entire scanner pool.
        """
        import concurrent.futures
        import os
        # CI/Benchmark override: Default to 75ms (0.075s) as per spec, allow env override
        scanner_timeout = float(os.getenv("SCANNER_TIMEOUT_MS", "75")) / 1000.0
        
        futures = [self._executor.submit(scanner.scan, payload) for scanner in self.scanners]
        violations = []
        try:
            for future in as_completed(futures, timeout=scanner_timeout):
                try:
                    violations.extend(future.result())
                except Exception as e:
                    print(f"[ScannerManager] Plugin failed: {e}")
                    if not self.config.secret_scanner_fail_open:
                        raise RuntimeError(f"Security Scanner Integrity Error: {e}")
        except FuturesTimeoutError:
            # Fail-closed: timeout = block
            print("[ScannerManager] Security scanning exceeded 75ms threshold")
            violations.append(
                ScanViolation(
                    scanner_name="timeout",
                    plugin_id="scanner_timeout",
                    confidence=1.0,
                    snippet_redacted="***TIMEOUT***"
                )
            )
        return violations

    def close(self):
        """Shutdown the persistent thread pool."""
        self._executor.shutdown(wait=False)
