import hmac
import hashlib
import time
from typing import Optional

def verify_bridge_signature(secret: str, signature: str, timestamp: str, body: bytes, window_seconds: int = 300) -> bool:
    """
    Verify HMAC-SHA256 signature for Cloud-to-Local Bridge requests.
    Signature = HMAC_SHA256(secret, timestamp + body)
    
    Args:
        secret: The shared BRIDGE_SECRET.
        signature: The hex signature from X-Bridge-Signature header.
        timestamp: The UTC timestamp from X-Bridge-Timestamp header.
        body: Raw request body bytes.
        window_seconds: Max age of the request to prevent replay attacks.
    """
    try:
        # 1. Replay Protection: Check if timestamp is within the window
        current_time = int(time.time())
        request_time = int(timestamp)
        
        if abs(current_time - request_time) > window_seconds:
            print(f"[HMAC] Request expired. Current: {current_time}, Request: {request_time}")
            return False
            
        # 2. Signature Verification
        msg = timestamp.encode() + body
        expected_mac = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        return hmac.compare_digest(expected_mac, signature)
    except Exception as e:
        print(f"[HMAC] Verification error: {e}")
        return False
