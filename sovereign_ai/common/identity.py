from .audit import Principal
from typing import Dict, Any, Optional

class IdentityHub:
    """
    Central hub for resolving principals and their attributes (v1.0.0-GA).
    In a production env, this would connect to Keycloak/OIDC.
    """
    
    @staticmethod
    def resolve_from_headers(headers: Dict[str, str]) -> Principal:
        """
        Resolves a Principal from incoming HTTP headers.
        Expected headers:
        - x-sovereign-principal: User ID
        - x-sovereign-tenant: Tenant ID
        - x-sovereign-roles: Comma-separated roles
        - x-sovereign-classifications: Comma-separated classifications
        """
        p_id = headers.get("x-sovereign-principal", "anonymous")
        t_id = headers.get("x-sovereign-tenant", "default")
        
        roles_raw = headers.get("x-sovereign-roles", "user")
        roles = [r.strip() for r in roles_raw.split(",")]
        
        class_raw = headers.get("x-sovereign-classifications", "public")
        classifications = [c.strip() for c in class_raw.split(",")]
        
        return Principal(
            id=p_id,
            tenant_id=t_id,
            roles=roles,
            classifications=classifications
        )

    @staticmethod
    def resolve_mock(user_type: str, tenant_id: str = "default") -> Principal:
        """Helper for demos/tests."""
        if user_type == "doctor":
            return Principal(id="dr_smith", tenant_id=tenant_id, roles=["doctor", "staff"], classifications=["public", "internal", "confidential"])
        if user_type == "nurse":
            return Principal(id="nurse_jones", tenant_id=tenant_id, roles=["nurse", "staff"], classifications=["public", "internal"])
        return Principal(id="anonymous", tenant_id=tenant_id, roles=["user"], classifications=["public"])
