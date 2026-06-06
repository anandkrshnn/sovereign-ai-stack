import logging
from typing import Optional
from sovereign_ai.common.hardware_trust import get_secure_anchor, SecureAnchor

logger = logging.getLogger("sovereign_ai.agent.tpm_signer")


class TPMSigner:
    """
    Hardware-bound signer for agent audit payloads.
    Wraps the Hardware Abstraction Layer (HAL) to provide
    secure, non-repudiable signing rooted in TPM 2.0.
    """

    def __init__(self, tenant_id: str = "default", backend: str = "auto"):
        self.tenant_id = tenant_id
        self.backend = backend
        self._anchor: Optional[SecureAnchor] = None

    @property
    def anchor(self) -> SecureAnchor:
        """Lazy-loaded hardware anchor."""
        if self._anchor is None:
            self._anchor = get_secure_anchor(self.tenant_id, backend=self.backend)
        return self._anchor

    def sign_event(self, payload: bytes) -> bytes:
        """
        Signs an audit event payload using the hardware-bound key.

        Args:
            payload: The raw bytes of the audit event.

        Returns:
            The raw signature bytes.
        """
        try:
            signature = self.anchor.sign_payload(payload)
            logger.debug(f"Payload signed successfully via {self.anchor.__class__.__name__}")
            return signature
        except Exception as e:
            logger.error(f"Hardware signing failed: {e}")
            raise RuntimeError(f"Failed to sign payload via hardware anchor: {e}")

    def get_attestation(self) -> str:
        """
        Retrieves the hardware attestation statement (quote/cert) for this signer.
        """
        return self.anchor.get_attestation_statement()

    @property
    def is_hardware_rooted(self) -> bool:
        """Checks if the signer is backed by real hardware."""
        return self.anchor.is_hardware


def sign_agent_payload(payload: bytes, tenant_id: str = "default") -> bytes:
    """
    Singleton-style helper for signing agent payloads.
    """
    signer = TPMSigner(tenant_id=tenant_id)
    return signer.sign_event(payload)
