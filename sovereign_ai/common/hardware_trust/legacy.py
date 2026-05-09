import hashlib
from typing import List, Any
from .base import SecureAnchor
from ..schemas import SigningAlgorithm, EvidenceType, AttestationQuote

class LegacyRawAnchor(SecureAnchor):
    """
    Legacy anchor for backward compatibility with non-attested keys.
    """
    def __init__(self, raw_key: bytes):
        self.raw_key = raw_key

    def sign_payload(self, payload: bytes) -> bytes:
        return hashlib.sha256(self.raw_key + payload).digest()

    def get_public_key(self) -> Any:
        # Legacy keys don't easily expose a cryptography object without re-parsing
        # But for mock purposes we can return a dummy or raise if needed
        return None 

    def get_public_key_pem(self) -> bytes:
        return b"LEGACY_PUB_KEY"

    def generate_quote(self, nonce: str, pcrs: List[int]) -> AttestationQuote:
        """Legacy keys return a mock quote."""
        return AttestationQuote(
            type=EvidenceType.MOCK_SIM,
            quote_data="legacy_mock_quote",
            pcr_values={p: "00"*32 for p in pcrs},
            firmware_version="Legacy_Key",
            runtime_measurement=hashlib.sha256(b"legacy").hexdigest(),
            signature="legacy_sig"
        )

    def get_signing_algorithm(self) -> SigningAlgorithm:
        return SigningAlgorithm.ED25519

    @property
    def is_hardware(self) -> bool:
        return False

__all__ = ["LegacyRawAnchor"]
