import logging
import os
import sys

from .base import SecureAnchor
from .legacy import LegacyRawAnchor
from .mock_sim import SoftwareSimulatorAnchor
from .tpm2_linux import HAS_PYTSS, TPM2LinuxAnchor
from .tpm2_windows import WindowsTPMAnchor

logger = logging.getLogger("hardware_trust")


class HardwareTrustError(RuntimeError):
    """Raised when production cannot establish a hardware-backed trust anchor."""


def get_secure_anchor(tenant_id: str, backend: str = "auto") -> SecureAnchor:
    """
    Hardware Abstraction Factory.
    Phase 3: Native detection and pluggable backends.
    """
    environment = os.getenv("SOVEREIGN_ENV", "development").strip().lower()
    production = environment in {"production", "prod"}
    allow_simulator = os.getenv("SOVEREIGN_ALLOW_SIMULATOR", "").lower() in {
        "1",
        "true",
        "yes",
    }

    if backend == "mock":
        if production and not allow_simulator:
            raise HardwareTrustError(
                "Software simulator is disabled in production; configure a TPM 2.0/HSM anchor."
            )
        return SoftwareSimulatorAnchor(tenant_id)

    if backend == "tpm2_linux" or (backend == "auto" and sys.platform == "linux"):
        if HAS_PYTSS:
            try:
                logger.info(f"Attempting Linux TPM2 initialization for tenant {tenant_id}")
                anchor: SecureAnchor = TPM2LinuxAnchor(tenant_id)
                if production and not anchor.is_hardware:
                    raise HardwareTrustError("Linux TPM 2.0 is present but not usable")
                return anchor
            except (HardwareTrustError, ImportError, OSError, RuntimeError) as e:
                logger.error("Linux TPM2 init failed: %s", e)
        else:
            logger.debug("Linux TPM2 driver (tpm2-pytss) not found.")

    if backend == "tpm2_windows" or (backend == "auto" and sys.platform == "win32"):
        try:
            if os.getenv("SOVEREIGN_FORCE_HW") == "1":
                logger.info(f"Attempting Windows TPM initialization for tenant {tenant_id}")
                anchor = WindowsTPMAnchor(tenant_id)
                if production and not anchor.is_hardware:
                    raise HardwareTrustError("Windows TPM is present but not usable")
                return anchor
        except (HardwareTrustError, ImportError, OSError, RuntimeError) as e:
            logger.error("Windows TPM init failed: %s", e)

    if production and not allow_simulator:
        raise HardwareTrustError(
            "No hardware trust anchor is available in production. "
            "Provision TPM 2.0/HSM and set the corresponding backend."
        )

    logger.debug(f"Using Software Simulator anchor for tenant {tenant_id}")
    return SoftwareSimulatorAnchor(tenant_id)


__all__ = [
    "HardwareTrustError",
    "LegacyRawAnchor",
    "SecureAnchor",
    "SoftwareSimulatorAnchor",
    "TPM2LinuxAnchor",
    "WindowsTPMAnchor",
    "get_secure_anchor",
]
