import sys
import os
import logging
from .base import SecureAnchor
from .mock_sim import SoftwareSimulatorAnchor
from .tpm2_windows import WindowsTPMAnchor
from .tpm2_linux import TPM2LinuxAnchor, HAS_PYTSS
from .legacy import LegacyRawAnchor

logger = logging.getLogger("hardware_trust")

def get_secure_anchor(tenant_id: str, backend: str = "auto") -> SecureAnchor:
    """
    Hardware Abstraction Factory.
    Phase 3: Native detection and pluggable backends.
    """
    if backend == "mock":
        return SoftwareSimulatorAnchor(tenant_id)
    
    if backend == "tpm2_linux" or (backend == "auto" and sys.platform == "linux"):
        if HAS_PYTSS:
            try:
                logger.info(f"Attempting Linux TPM2 initialization for tenant {tenant_id}")
                return TPM2LinuxAnchor(tenant_id)
            except Exception as e:
                logger.error(f"Linux TPM2 init failed: {e}. Falling back to simulation.")
        else:
            logger.debug("Linux TPM2 driver (tpm2-pytss) not found.")

    if backend == "tpm2_windows" or (backend == "auto" and sys.platform == "win32"):
        try:
            if os.getenv("SOVEREIGN_FORCE_HW") == "1":
                logger.info(f"Attempting Windows TPM initialization for tenant {tenant_id}")
                return WindowsTPMAnchor(tenant_id)
        except Exception as e:
            logger.error(f"Windows TPM init failed: {e}. Falling back to simulation.")

    # Default fallback
    logger.debug(f"Using Software Simulator anchor for tenant {tenant_id}")
    return SoftwareSimulatorAnchor(tenant_id)

__all__ = [
    "SecureAnchor",
    "SoftwareSimulatorAnchor",
    "WindowsTPMAnchor",
    "TPM2LinuxAnchor",
    "LegacyRawAnchor",
    "get_secure_anchor"
]
