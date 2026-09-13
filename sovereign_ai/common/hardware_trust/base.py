from abc import ABC, abstractmethod
from typing import Any, List

from ..schemas import AttestationQuote, SigningAlgorithm


class SecureAnchor(ABC):
    """
    Abstract Base Class for hardware-anchored trust.
    Phase 3: Hardware-Native Abstraction.
    """

    @abstractmethod
    def sign_payload(self, payload: bytes) -> bytes:
        """Signs a payload using the anchor's private key."""

    def sign(self, payload: bytes) -> bytes:
        """Alias for sign_payload for backward compatibility."""
        return self.sign_payload(payload)

    @abstractmethod
    def get_public_key_pem(self) -> bytes:
        """Returns the public key in PEM format."""

    @abstractmethod
    def get_public_key(self) -> Any:
        """Returns the raw cryptography public key object."""

    @abstractmethod
    def generate_quote(self, nonce: str, pcrs: list[int]) -> AttestationQuote:
        """Generates a cryptographically signed hardware quote (RATS Evidence)."""

    @abstractmethod
    def get_signing_algorithm(self) -> SigningAlgorithm:
        """Returns the algorithm used by this anchor."""

    @abstractmethod
    def seal_key(self, plaintext_key: bytes) -> bytes:
        """Seals a plaintext key using the anchor's security boundaries."""

    @abstractmethod
    def unseal_key(self, sealed_key: bytes) -> bytes:
        """Unseals a sealed key using the anchor's security boundaries."""

    @property
    def algorithm(self) -> SigningAlgorithm:
        """Property access for signing algorithm."""
        return self.get_signing_algorithm()

    @property
    @abstractmethod
    def is_hardware(self) -> bool:
        """Returns True if this is a real hardware-anchored key."""

    def get_attestation_statement(self) -> bytes:
        """
        Returns a hardware attestation statement (e.g., TPM certificate chain).
        Default implementation returns an empty statement.
        """
        return b""

    def get_status(self) -> dict:
        """Returns a diagnostic status of the anchor."""
        return {"type": self.__class__.__name__, "available": True, "details": "Active"}


__all__ = ["SecureAnchor"]
