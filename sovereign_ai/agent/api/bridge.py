import hmac
import hashlib
import time
import json
from typing import Dict, Any, Optional
from localagent.config import Config

class BridgeSecurityManager:
    """
    Handles HMAC-SHA256 signature verification and replay protection for the Bridge ingress.
    """
    
    def __init__(self, secret: str = None):
        self.secret = secret or Config.default().bridge_secret
        self.processed_signatures = set() # Volatile cache for replay protection (per session)
        self.max_age_seconds = 30

    def verify_request(self, payload: str, signature: str, timestamp: str) -> bool:
        """
        Validates the request:
        1. Signature matches HMAC-SHA256(secret, timestamp + payload).
        2. Timestamp is within the 30s window.
        3. Signature has not been used before (Replay Protection).
        """
        if not signature or not timestamp:
            return False

        try:
            ts_float = float(timestamp)
            current_ts = time.time()
            
            # 1. Age check
            if abs(current_ts - ts_float) > self.max_age_seconds:
                print(f"[Bridge] REJECTED: Request too old (Age: {current_ts - ts_float:.1f}s)")
                return False

            # 2. Replay check
            if signature in self.processed_signatures:
                print(f"[Bridge] REJECTED: Replay detected for signature {signature[:10]}...")
                return False

            # 3. Signature check
            message = f"{timestamp}{payload}".encode('utf-8')
            expected_signature = hmac.new(
                self.secret.encode('utf-8'),
                message,
                hashlib.sha256
            ).hexdigest()

            if hmac.compare_digest(expected_signature, signature):
                self.processed_signatures.add(signature)
                # Cleanup if cache gets too large (simple strategy)
                if len(self.processed_signatures) > 1000:
                    self.processed_signatures.clear()
                return True
            
            print(f"[Bridge] REJECTED: Invalid signature")
            return False
            
        except (ValueError, TypeError) as e:
            print(f"[Bridge] REJECTED: Invalid timestamp format ({e})")
            return False

def sign_payload(payload: str, secret: str, timestamp: float = None) -> Dict[str, str]:
    """Helper for testing and client implementation."""
    if timestamp is None:
        timestamp = time.time()
    ts_str = str(timestamp)
    message = f"{ts_str}{payload}".encode('utf-8')
    signature = hmac.new(
        secret.encode('utf-8'),
        message,
        hashlib.sha256
    ).hexdigest()
    return {"signature": signature, "timestamp": ts_str}
