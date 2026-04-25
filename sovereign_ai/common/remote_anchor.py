import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class AnchorReceipt:
    proof: str
    backend: str
    timestamp: float
    tenant_id: str

class RemoteAnchorService:
    """
    Sovereign Remote Anchor Service (v1.1.0-alpha).
    Provides non-repudiation by pinning local chain heads to external backends.
    """
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.backend_type = self.config.get("backend", "none")

    def anchor(self, tenant_id: str, chain_head: str) -> Optional[AnchorReceipt]:
        """Pins the current chain head to the configured remote backend."""
        if self.backend_type == "git":
            return self._git_anchor(tenant_id, chain_head)
        elif self.backend_type == "ipfs":
            return self._ipfs_anchor(tenant_id, chain_head)
        elif self.backend_type == "none":
            return None
        else:
            raise ValueError(f"Unknown remote anchor backend: {self.backend_type}")

    def _git_anchor(self, tenant_id: str, chain_head: str) -> AnchorReceipt:
        """Anchors via Git commit in an enterprise repository."""
        try:
            import git
            repo_path = self.config.get("git_repo_path", ".")
            repo = git.Repo(repo_path)
            
            # Create/Update a witness file
            witness_dir = Path(repo_path) / ".sovereign_witness"
            witness_dir.mkdir(exist_ok=True)
            witness_file = witness_dir / f"{tenant_id}.anchor"
            
            witness_data = {
                "tenant_id": tenant_id,
                "chain_head": chain_head,
                "timestamp": time.time()
            }
            witness_file.write_text(json.dumps(witness_data))
            
            # Commit
            repo.index.add([str(witness_file)])
            commit = repo.index.commit(f"Forensic Anchor [{tenant_id}]: {chain_head}")
            
            return AnchorReceipt(
                proof=commit.hexsha,
                backend="git",
                timestamp=time.time(),
                tenant_id=tenant_id
            )
        except Exception as e:
            # For v1.0.0, we fail gracefully to ensure local availability isn't blocked
            print(f"Warning: Remote Git Anchor failed: {e}")
            return None

    def _ipfs_anchor(self, tenant_id: str, chain_head: str) -> AnchorReceipt:
        """Anchors via IPFS CID pinning (Placeholder for v1.1.0)."""
        # Logic to pin via Infura/Pinata/Local Node
        return AnchorReceipt(
            proof="ipfs_cid_placeholder",
            backend="ipfs",
            timestamp=time.time(),
            tenant_id=tenant_id
        )
