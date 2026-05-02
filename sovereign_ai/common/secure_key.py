"""
Secure Key Management with Ed25519 Support

Manages both:
1. Symmetric keys (Fernet) for data encryption
2. Asymmetric keys (Ed25519) for audit signing
"""

import keyring
import os
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
import base64


class SecureKeyManager:
    """
    Manages encryption and signing keys via OS keyring.
    
    Keys stored:
    - Session key (symmetric Fernet)
    - Signing key (asymmetric Ed25519)
    """
    
    SERVICE_NAME = "sovereign-ai-stack"
    SESSION_KEY_NAME = "session_encryption_key"
    SIGNING_KEY_NAME = "ed25519_signing_key"
    
    def __init__(self, tenant_id: str):
        """
        Initialize key manager for tenant.
        
        Args:
            tenant_id: Tenant identifier (used as keyring namespace)
        """
        self.tenant_id = tenant_id
        self.keyring_username = f"{tenant_id}_keys"
    
    def get_or_create_session_key(self) -> bytes:
        """
        Get or create Fernet session key.
        
        Returns 32-byte key suitable for Fernet encryption.
        """
        # Try to retrieve from keyring
        stored_key = keyring.get_password(
            self.SERVICE_NAME,
            f"{self.keyring_username}_{self.SESSION_KEY_NAME}"
        )
        
        if stored_key:
            return base64.urlsafe_b64decode(stored_key.encode())
        
        # Generate new key
        key = Fernet.generate_key()
        
        # Store in keyring
        keyring.set_password(
            self.SERVICE_NAME,
            f"{self.keyring_username}_{self.SESSION_KEY_NAME}",
            base64.urlsafe_b64encode(key).decode()
        )
        
        return key
    
    def get_or_create_signing_key(self) -> ed25519.Ed25519PrivateKey:
        """
        Get or create Ed25519 signing key.
        
        Returns Ed25519 private key for audit signing.
        """
        # Try to retrieve from keyring
        stored_key_pem = keyring.get_password(
            self.SERVICE_NAME,
            f"{self.keyring_username}_{self.SIGNING_KEY_NAME}"
        )
        
        if stored_key_pem:
            # Deserialize from PEM
            private_key = serialization.load_pem_private_key(
                stored_key_pem.encode(),
                password=None
            )
            return private_key
        
        # Generate new Ed25519 keypair
        private_key = ed25519.Ed25519PrivateKey.generate()
        
        # Serialize to PEM for storage
        private_key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        
        # Store in keyring
        keyring.set_password(
            self.SERVICE_NAME,
            f"{self.keyring_username}_{self.SIGNING_KEY_NAME}",
            private_key_pem
        )
        
        return private_key
    
    def get_fernet(self) -> Fernet:
        """Get Fernet cipher for symmetric encryption."""
        key = self.get_or_create_session_key()
        return Fernet(key)
    
    def rotate_keys(self):
        """
        Rotate all keys (use with caution).
        
        WARNING: Rotating signing key will break audit chain verification
        for existing events. Only use for new tenants or emergency scenarios.
        """
        # Delete old keys from keyring
        try:
            keyring.delete_password(
                self.SERVICE_NAME,
                f"{self.keyring_username}_{self.SESSION_KEY_NAME}"
            )
        except:
            pass
        
        try:
            keyring.delete_password(
                self.SERVICE_NAME,
                f"{self.keyring_username}_{self.SIGNING_KEY_NAME}"
            )
        except:
            pass
        
        # Regenerate
        self.get_or_create_session_key()
        self.get_or_create_signing_key()
