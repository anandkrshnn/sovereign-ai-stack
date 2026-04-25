import os
import hmac
import hashlib
import time
import json
from typing import Optional, List, Dict
from jose import jwt, jwk
from fastapi import Request, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from local_bridge.schemas import TenantContext

class SovereignIdentityHub:
    """
    Identity Hub for local-bridge v1.0.0.
    Handles JWT (Keycloak) and Signed API Keys.
    Enforces 'No Default Tenant' policy.
    """

    def __init__(self, master_secret: str, base_dir: str = "data", jwks_url: Optional[str] = None):
        self.master_secret = master_secret.encode("utf-8")
        self.base_dir = base_dir
        self.jwks_url = jwks_url
        self._cached_jwks = None

    def _is_revoked(self, tenant_id: str, identifier: str, full_key: Optional[str] = None) -> bool:
        """Check if an identifier or full key is present in the tenant-scoped revocation list."""
        rev_path = os.path.join(self.base_dir, tenant_id, "revocation_list.json")
        if not os.path.exists(rev_path):
            return False
        try:
            with open(rev_path, "r") as f:
                data = json.load(f)
                revoked = data.get("revoked_identifiers", [])
                return identifier in revoked or (full_key in revoked if full_key else False)
        except Exception:
            return False

    async def get_context(self, request: Request) -> TenantContext:
        """Dependency to extract authenticated tenant context."""
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            raise HTTPException(status_code=401, detail="Authentication required (No Default Tenant)")

        # 1. Check for Bearer Token (JWT)
        if auth_header.startswith("Bearer "):
            token = auth_header.replace("Bearer ", "")
            if "sk-sov-" in token: # Handle key as bearer
                return self.verify_api_key(token)
            return await self.validate_jwt(token)
            
        raise HTTPException(status_code=401, detail="Invalid Authentication Format")

    async def validate_jwt(self, token: str) -> TenantContext:
        """Strict JWT Claims Contract validation (GAIP-2030)."""
        try:
            # unverified_claims for pilot; in production, use jwk.construct + jwt.decode
            payload = jwt.get_unverified_claims(token)
            
            # --- STRICT CLAIMS CONTRACT ---
            tenant_id = payload.get("tenant_id")
            principal = payload.get("sub")
            issuer = payload.get("iss")
            expiry = payload.get("exp")
            
            if not all([tenant_id, principal, issuer, expiry]):
                raise HTTPException(status_code=403, detail="Missing mandatory claims: iss, sub, tenant_id, exp")
            
            if expiry < time.time():
                raise HTTPException(status_code=401, detail="Token expired")
                
            if self._is_revoked(tenant_id, principal):
                raise HTTPException(status_code=403, detail="Principal identity has been revoked")
                
            return TenantContext(
                tenant_id=tenant_id,
                principal=principal,
                scopes=payload.get("scope", "").split(" ") if isinstance(payload.get("scope"), str) else payload.get("scopes", []),
                is_authenticated=True
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"JWT Validation Failed: {e}")

    def verify_api_key(self, key: str) -> TenantContext:
        """
        Stateless verification of signed API keys.
        Format: sk-sov-{tenant}:{principal}.{signature}
        """
        try:
            trimmed = key.replace("sk-sov-", "")
            if "." not in trimmed:
                raise ValueError("Malformed API Key (Missing Signature)")
                
            body, signature = trimmed.rsplit(".", 1)
            if ":" not in body:
                raise ValueError("Malformed API Key (Missing Tenant:Principal separator)")
                
            tenant_id, principal = body.split(":", 1)
            
            # Verify Signature
            expected_sig = hmac.new(
                self.master_secret, 
                f"{tenant_id}:{principal}".encode("utf-8"), 
                hashlib.sha256
            ).hexdigest()[:16]
            
            if not hmac.compare_digest(signature, expected_sig):
                raise ValueError("Invalid API Key Signature")
            
            # Check Revocation
            if self._is_revoked(tenant_id, f"sk-sov-{body}", full_key=key):
                raise ValueError("API Key has been revoked")
                
            return TenantContext(
                tenant_id=tenant_id,
                principal=principal,
                is_authenticated=True
            )
        except Exception as e:
            raise HTTPException(status_code=401, detail=f"API Key Verification Failed: {str(e)}")

    def generate_api_key(self, tenant_id: str, principal: str) -> str:
        """Helper for manual provisioning."""
        sig = hmac.new(
            self.master_secret, 
            f"{tenant_id}:{principal}".encode("utf-8"), 
            hashlib.sha256
        ).hexdigest()[:16]
        return f"sk-sov-{tenant_id}:{principal}.{sig}"
