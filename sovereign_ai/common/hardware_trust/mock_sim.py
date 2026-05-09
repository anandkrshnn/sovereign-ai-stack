import os
import hashlib
import logging
from typing import List
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

from .base import SecureAnchor
from ..schemas import SigningAlgorithm, EvidenceType, AttestationQuote

class SoftwareSimulatorAnchor(SecureAnchor):
    """
    High-fidelity software simulator for hardware trust.
    Uses Ed25519 keys stored in a local .trust_anchor file.
    """
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.key_path = f".trust_anchor_{tenant_id}.key"
        self._private_key = self._load_or_generate()

    def _load_or_generate(self) -> ed25519.Ed25519PrivateKey:
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as f:
                return ed25519.Ed25519PrivateKey.from_private_bytes(f.read())
        
        key = ed25519.Ed25519PrivateKey.generate()
        with open(self.key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption()
            ))
        return key

    def sign_payload(self, payload: bytes) -> bytes:
        return self._private_key.sign(payload)

    def get_public_key(self) -> ed25519.Ed25519PublicKey:
        return self._private_key.public_key()

    def get_public_key_pem(self) -> bytes:
        return self.get_public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def generate_quote(self, nonce: str, pcrs: List[int]) -> AttestationQuote:
        """Simulates a RATS-compliant hardware quote."""
        return AttestationQuote(
            type=EvidenceType.MOCK_SIM,
            quote_data=hashlib.sha256(nonce.encode()).hexdigest(),
            pcr_values={p: hashlib.sha256(f"pcr_{p}_val".encode()).hexdigest() for p in pcrs},
            firmware_version="SoftwareSimulator_v1.0",
            runtime_measurement=hashlib.sha256(b"simulated_runtime_state").hexdigest(),
            signature=hashlib.sha256(b"sim_sig").hexdigest()
        )

    def get_signing_algorithm(self) -> SigningAlgorithm:
        return SigningAlgorithm.ED25519

    @property
    def is_hardware(self) -> bool:
        return False

__all__ = ["SoftwareSimulatorAnchor"]
