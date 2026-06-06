import hashlib
from typing import Any, List

from cryptography.hazmat.primitives import serialization

from ..schemas import AttestationQuote, EvidenceType, SigningAlgorithm
from .base import SecureAnchor


class LegacyRawAnchor(SecureAnchor):
    """
    Legacy anchor for backward compatibility with non-attested keys.
    Supports both raw bytes (HMAC-style) and cryptography key objects.
    """

    def __init__(self, raw_key: Any):
        self.raw_key = raw_key

    def sign_payload(self, payload: bytes) -> bytes:
        if hasattr(self.raw_key, "sign"):
            return self.raw_key.sign(payload)
        return hashlib.sha256(self.raw_key + payload).digest()

    def get_public_key(self) -> Any:
        if hasattr(self.raw_key, "public_key"):
            return self.raw_key.public_key()
        return None

    def get_public_key_pem(self) -> bytes:
        pub = self.get_public_key()
        if pub:
            return pub.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
        return b"LEGACY_PUB_KEY"

    def generate_quote(self, nonce: str, pcrs: List[int]) -> AttestationQuote:
        """Legacy keys return a mock quote."""
        return AttestationQuote(
            type=EvidenceType.MOCK_SIM,
            quote_data="legacy_mock_quote",
            pcr_values={p: "00" * 32 for p in pcrs},
            firmware_version="Legacy_Key",
            runtime_measurement=hashlib.sha256(b"legacy").hexdigest(),
            signature="legacy_sig",
        )

    def get_signing_algorithm(self) -> SigningAlgorithm:
        return SigningAlgorithm.ED25519

    def _get_encryption_key(self) -> bytes:
        if hasattr(self.raw_key, "private_bytes"):
            try:
                # Try raw format first (e.g., Ed25519)
                raw_bytes = self.raw_key.private_bytes(
                    encoding=serialization.Encoding.Raw,
                    format=serialization.PrivateFormat.Raw,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            except Exception:
                try:
                    # Fallback to DER/PKCS8 (e.g., RSA, EC)
                    raw_bytes = self.raw_key.private_bytes(
                        encoding=serialization.Encoding.DER,
                        format=serialization.PrivateFormat.PKCS8,
                        encryption_algorithm=serialization.NoEncryption(),
                    )
                except Exception:
                    raw_bytes = b"fallback_legacy_raw_bytes"
        elif isinstance(self.raw_key, bytes):
            raw_bytes = self.raw_key
        else:
            raw_bytes = str(self.raw_key).encode()
        return hashlib.sha256(raw_bytes).digest()

    def seal_key(self, plaintext_key: bytes) -> bytes:
        """Seals a plaintext key using a derived key (AES CFB)."""
        derived_key = self._get_encryption_key()
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        iv = b"\x00" * 16
        encryptor = Cipher(
            algorithms.AES(derived_key), modes.CFB(iv), backend=default_backend()
        ).encryptor()
        return encryptor.update(plaintext_key) + encryptor.finalize()

    def unseal_key(self, sealed_key: bytes) -> bytes:
        """Unseals a key using a derived key (AES CFB)."""
        derived_key = self._get_encryption_key()
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

        iv = b"\x00" * 16
        decryptor = Cipher(
            algorithms.AES(derived_key), modes.CFB(iv), backend=default_backend()
        ).decryptor()
        return decryptor.update(sealed_key) + decryptor.finalize()

    @property
    def is_hardware(self) -> bool:
        return False


__all__ = ["LegacyRawAnchor"]
