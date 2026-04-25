import time
from typing import Dict, Any

class ResourceQuota:
    """
    Implements session-based resource bounding to prevent DoS (Denial of Service).
    Strictly follows the v0.2 limits: 1,000 write ops and 100MB per session.
    """
    
    # Hardcoded v0.2 defaults
    MAX_WRITE_OPS = 1000
    MAX_WRITE_BYTES = 100 * 1024 * 1024 # 100MB

    def __init__(self):
        self.write_ops = 0
        self.write_bytes = 0
        self.start_time = time.time()

    def check_and_update(self, intent: str, resource_size: int = 0) -> bool:
        """
        Validates the operation against current session quotas.
        Returns True if the operation is within limits.
        """
        if intent in ["write_file", "append_to_file"]:
            new_ops = self.write_ops + 1
            new_bytes = self.write_bytes + resource_size
            
            if new_ops > self.MAX_WRITE_OPS:
                print(f"[ResourceQuota] REJECTED: Write operations limit ({self.MAX_WRITE_OPS}) exceeded.")
                return False
                
            if new_bytes > self.MAX_WRITE_BYTES:
                print(f"[ResourceQuota] REJECTED: Write byte limit ({self.MAX_WRITE_BYTES // 1024 // 1024}MB) exceeded.")
                return False
                
            # Commit the usage
            self.write_ops = new_ops
            self.write_bytes = new_bytes
            
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Returns current usage statistics for status reporting."""
        return {
            "write_ops": self.write_ops,
            "write_bytes": self.write_bytes,
            "uptime_s": time.time() - self.start_time
        }
