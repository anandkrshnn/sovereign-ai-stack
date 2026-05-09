import os
import logging
import hashlib
from abc import ABC, abstractmethod
from typing import Optional, Any, List, Union
from cryptography.hazmat.primitives.asymmetric import ed25519, ec
from cryptography.hazmat.primitives import serialization, hashes

from ..schemas import SigningAlgorithm, EvidenceType, AttestationQuote

class SecureAnchor(ABC):
    """
    Abstract Base Class for hardware-anchored trust.
    Phase 3: Hardware-Native Abstraction.
    """
    @abstractmethod
    def sign_payload(self, payload: bytes) -> bytes:
        """Signs a payload using the anchor's private key."""
        pass

    def sign(self, payload: bytes) -> bytes:
        """Alias for sign_payload for backward compatibility."""
        return self.sign_payload(payload)

    @abstractmethod
    def get_public_key_pem(self) -> bytes:
        """Returns the public key in PEM format."""
        pass

    @abstractmethod
    def get_public_key(self) -> Any:
        """Returns the raw cryptography public key object."""
        pass

    @abstractmethod
    def generate_quote(self, nonce: str, pcrs: List[int]) -> AttestationQuote:
        """Generates a cryptographically signed hardware quote (RATS Evidence)."""
        pass

    @abstractmethod
    def get_signing_algorithm(self) -> SigningAlgorithm:
        """Returns the algorithm used by this anchor."""
        pass

    @property
    def algorithm(self) -> SigningAlgorithm:
        """Property access for signing algorithm."""
        return self.get_signing_algorithm()

    @property
    @abstractmethod
    def is_hardware(self) -> bool:
        """Returns True if this is a real hardware-anchored key."""
        pass

    def get_attestation_statement(self) -> bytes:
        """
        Returns a hardware attestation statement (e.g., TPM certificate chain).
        Default implementation returns an empty statement.
        """
        return b""

__all__ = ["SecureAnchor"]
