"""
sovereign_ai.agent.forensics
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Cryptographic non-repudiation layer for the Sovereign AI Agent.

Exports:
    AuditChainManager  — SHA-256 hash-chained JSONL audit log with anchor verification
    SecureKeyManager   — OS-keyring / Fernet key derivation and rotation
    VaultContext       — Vault path resolver and key bootstrapper

Phase 1 consolidation note:
    This package is the canonical home for all forensics logic
    previously scattered across local-agent-v0.2/forensics/.
    Ed25519 signing (sign_payload / verify_payload) is in secure_key.py.
"""

from .audit_chain import AuditChainManager
from .secure_key import SecureKeyManager
from .vault_context import VaultContext

__all__ = [
    "AuditChainManager",
    "SecureKeyManager",
    "VaultContext",
]
