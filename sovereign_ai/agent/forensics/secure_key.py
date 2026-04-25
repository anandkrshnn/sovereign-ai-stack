import keyring
import os
from pathlib import Path
import base64
from typing import Optional

class SecureKeyManager:
    """
    Manages the session encryption keys using secure enclaves (Windows Credential Manager).
    Implements a strict fallback chain: Keyring -> Prompt.
    """
    
    SERVICE_NAME = "localagent"
    KEY_NAME = "trace_key"

    @staticmethod
    def get_trace_key() -> str:
        """
        Retrieves the trace encryption key from the secure store.
        If missing, prompts the user and stores it.
        """
        key = keyring.get_password(SecureKeyManager.SERVICE_NAME, SecureKeyManager.KEY_NAME)
        if key:
            return key
        
        return SecureKeyManager._provision_key()

    @staticmethod
    def _provision_key() -> str:
        """
        Interactive fallback: Prompts the user for a passphrase on first-use.
        Stores the resulting key in the OS keyring.
        """
        import getpass
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        print("\n" + "="*60)
        print("SECURE KEY PROVISIONING REQUIRED")
        print("="*60)
        print("LocalAgent needs a session passphrase to encrypt your audit logs.")
        print("This passphrase will be stored in the Windows Credential Manager.")
        print("="*60)
        
        passphrase = getpass.getpass("Enter master passphrase: ")
        
        # Derive a 32-byte key from the passphrase
        salt = b'SovereignLocalAgentV0.2' # Static salt for session persistence
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key_bytes = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
        
        # Store in keyring
        try:
            keyring.set_password(
                SecureKeyManager.SERVICE_NAME, 
                SecureKeyManager.KEY_NAME, 
                key_bytes.decode()
            )
            print("[SecureKeyManager] Key successfully provisioned and stored in Windows Enclave.")
        except Exception as e:
            print(f"[SecureKeyManager] WARNING: Failed to store key in keyring ({e}). Key will be volatile.")
            
        return key_bytes.decode()

    @staticmethod
    def wrap_key_to_vault(vault_root: Path, master_passphrase: str):
        """
        v8.0 Sovereign Staple: Encrypts the current session key with the vault password.
        Saves to vault_root/audit.key.
        """
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        # 1. Get the current active session key (from enclave)
        session_key = SecureKeyManager.get_trace_key()
        
        # 2. Derive a 'wrapper' key from the master passphrase
        # Use vault_salt if present, else generate and save
        salt_path = vault_root / ".vault_salt"
        if salt_path.exists():
            salt = salt_path.read_bytes()
        else:
            salt = os.urandom(16)
            salt_path.write_bytes(salt)
            
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        wrapper_key = base64.urlsafe_b64encode(kdf.derive(master_passphrase.encode()))
        
        # 3. Encrypt the session key with the wrapper key
        f = Fernet(wrapper_key)
        wrapped_key = f.encrypt(session_key.encode())
        
        # 4. Save to audit.key
        (vault_root / "audit.key").write_bytes(wrapped_key)

    @staticmethod
    def unwrap_key_from_vault(vault_root: Path, master_passphrase: str) -> str:
        """
        v8.0 Forensic Recovery: Decrypts the session key using the master password.
        Enables offline auditing without OS keyring access.
        """
        from cryptography.fernet import Fernet
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        
        key_path = vault_root / "audit.key"
        salt_path = vault_root / ".vault_salt"
        if not key_path.exists() or not salt_path.exists():
            raise FileNotFoundError("Sovereign audit key or salt missing from vault.")
            
        salt = salt_path.read_bytes()
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        wrapper_key = base64.urlsafe_b64encode(kdf.derive(master_passphrase.encode()))
        
        f = Fernet(wrapper_key)
        wrapped_data = key_path.read_bytes()
        return f.decrypt(wrapped_data).decode()

    @staticmethod
    def create_forensic_key_manager(vault_root: Path) -> 'VaultKeyManager':
        """
        Explicit investigative bridge: Provisions a KeyManager from the OS enclave.
        This is an operator-invoked action for authorized decryption.
        """
        from localagent.forensics.vault_key_manager import VaultKeyManager
        key = SecureKeyManager.get_trace_key()
        return VaultKeyManager(vault_root, key)

    @staticmethod
    def clear_key():
        """Optionally clear the key (e.g. on logout/hard reset)."""
        try:
            keyring.delete_password(SecureKeyManager.SERVICE_NAME, SecureKeyManager.KEY_NAME)
        except Exception:
            pass
