import os
import logging
import hashlib
from abc import ABC, abstractmethod
from typing import Optional, Any
from cryptography.hazmat.primitives.asymmetric import ed25519, ec
from cryptography.hazmat.primitives import serialization, hashes
from .schemas import SigningAlgorithm
import ctypes
import sys

# Windows-specific imports
if sys.platform == "win32":
    from ctypes import wintypes
else:
    wintypes = None

logger = logging.getLogger(__name__)

class SecureAnchor(ABC):
    """
    Abstract interface for Hardware Root of Trust (TPM/HSM).
    Encapsulates key generation and signing without exposing private keys to the OS.
    """
    
    @property
    @abstractmethod
    def algorithm(self) -> SigningAlgorithm:
        """Return the signing algorithm used by this anchor."""
        pass

    @abstractmethod
    def sign(self, data: bytes) -> bytes:
        """Sign data using the hardware-bound key."""
        pass

    @abstractmethod
    def get_public_key(self) -> Any:
        """Retrieve the public key associated with the anchor."""
        pass

    @abstractmethod
    def get_status(self) -> dict:
        """Return diagnostic status of the anchor."""
        pass

class SoftwareSimulatorAnchor(SecureAnchor):
    """
    A simulated TPM anchor that stores the key in a local, hidden, 
    permission-locked file to simulate a hardware-protected enclave.
    """
    
    def __init__(self, tenant_id: str, storage_path: str = ".tpm_sim"):
        self.tenant_id = tenant_id
        self.storage_path = os.path.expanduser(storage_path)
        self.key_file = os.path.join(self.storage_path, f"{tenant_id}.key")
        
        if not os.path.exists(self.storage_path):
            os.makedirs(self.storage_path, mode=0o700)
            
        self._private_key = self._load_or_generate()

    @property
    def algorithm(self) -> SigningAlgorithm:
        return SigningAlgorithm.ED25519

    def _load_or_generate(self) -> ed25519.Ed25519PrivateKey:
        if os.path.exists(self.key_file):
            try:
                with open(self.key_file, "rb") as f:
                    pem_data = f.read()
                return serialization.load_pem_private_key(pem_data, password=None)
            except Exception as e:
                logger.error(f"Failed to load simulated TPM key: {e}")
                
        # Generate new key
        logger.info(f"Generating new hardware-bound key for {self.tenant_id}...")
        key = ed25519.Ed25519PrivateKey.generate()
        pem_data = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        with open(self.key_file, "wb") as f:
            f.write(pem_data)
            
        # In a real TPM, we would set file permissions to 400 or use ioctl to lock
        os.chmod(self.key_file, 0o400)
        return key

    def sign(self, data: bytes) -> bytes:
        """Perform signing inside the 'enclave'."""
        return self._private_key.sign(data)

    def get_public_key(self) -> ed25519.Ed25519PublicKey:
        return self._private_key.public_key()

    def get_status(self) -> dict:
        return {
            "type": "Software Simulator",
            "available": True,
            "details": "Permission-locked file (simulation)"
        }

class WindowsTPMAnchor(SecureAnchor):
    """
    Hardware Root of Trust via Windows Platform Crypto Provider (TPM 2.0).
    Uses P-256 (ECDSA) anchored in the hardware TPM.
    """
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.key_name = f"sovereign_ai_{tenant_id}_audit_v1"
        self._hKey = None
        self._hProv = None
        self._is_hardware = False
        
        try:
            if sys.platform != "win32":
                raise RuntimeError("TPM anchoring only supported on Windows")
            self._init_tpm()
            self._is_hardware = True
        except Exception as e:
            logger.warning(f"TPM initialization failed, falling back to simulator: {e}")
            self._private_key = self._load_from_tpm_sim()

    @property
    def algorithm(self) -> SigningAlgorithm:
        return SigningAlgorithm.P256

    def _init_tpm(self):
        ncrypt = ctypes.windll.ncrypt
        MS_PLATFORM_CRYPTO_PROVIDER = "Microsoft Platform Crypto Provider"
        NCRYPT_SUCCESS = 0
        
        hProv = wintypes.HANDLE()
        status = ncrypt.NCryptOpenStorageProvider(ctypes.byref(hProv), MS_PLATFORM_CRYPTO_PROVIDER, 0)
        if status != NCRYPT_SUCCESS:
            raise RuntimeError(f"Could not open TPM provider: {hex(status & 0xFFFFFFFF)}")
        self._hProv = hProv

        hKey = wintypes.HANDLE()
        # Try to open existing key
        status = ncrypt.NCryptOpenKey(hProv, ctypes.byref(hKey), self.key_name, 0, 0)
        
        if status != NCRYPT_SUCCESS:
            # Create new key if not found
            logger.info(f"Creating new TPM-bound key: {self.key_name}")
            status = ncrypt.NCryptCreatePersistedKey(hProv, ctypes.byref(hKey), "ECDSA_P256", self.key_name, 0, 0)
            if status != NCRYPT_SUCCESS:
                raise RuntimeError(f"Could not create TPM key: {hex(status & 0xFFFFFFFF)}")
            
            status = ncrypt.NCryptFinalizeKey(hKey, 0)
            if status != NCRYPT_SUCCESS:
                raise RuntimeError(f"Could not finalize TPM key: {hex(status & 0xFFFFFFFF)}")
        
        self._hKey = hKey

    def _load_from_tpm_sim(self) -> ec.EllipticCurvePrivateKey:
        # Simulate TPM hardware binding
        sim_path = os.path.expanduser("~/.tpm_enclave")
        if not os.path.exists(sim_path):
            os.makedirs(sim_path, mode=0o700)
        
        key_path = os.path.join(sim_path, f"{self.tenant_id}_p256.key")
        if os.path.exists(key_path):
            with open(key_path, "rb") as f:
                return serialization.load_pem_private_key(f.read(), password=None)
        
        logger.info(f"Generating TPM-simulated P-256 key for {self.tenant_id}...")
        key = ec.generate_private_key(ec.SECP256R1())
        with open(key_path, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        return key

    def sign(self, data: bytes) -> bytes:
        """Sign data using ECDSA P-256 (TPM or Sim) with retry logic."""
        if not self._is_hardware:
            return self._private_key.sign(data, ec.ECDSA(hashes.SHA256()))
        
        # Native TPM Signing
        import time
        from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
        
        ncrypt = ctypes.windll.ncrypt
        NCRYPT_SUCCESS = 0
        NTE_BUSY = 0x80090013
        NTE_DEVICE_NOT_READY = 0x80090030
        
        # Data must be hashed for TPM
        digest = hashlib.sha256(data).digest()
        
        max_retries = 3
        retry_delay = 0.05 # 50ms base
        
        for attempt in range(max_retries + 1):
            try:
                cbResult = wintypes.DWORD(0)
                status = ncrypt.NCryptSignHash(self._hKey, None, digest, len(digest), None, 0, ctypes.byref(cbResult), 0)
                
                # Check for transient hardware errors
                if status in (NTE_BUSY, NTE_DEVICE_NOT_READY) and attempt < max_retries:
                    logger.warning(f"TPM busy (status {hex(status & 0xFFFFFFFF)}), retrying in {retry_delay:.3f}s...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                    
                if status != NCRYPT_SUCCESS:
                    raise RuntimeError(f"TPM Sign size failed: {hex(status & 0xFFFFFFFF)}")
                    
                sig_buf = ctypes.create_string_buffer(cbResult.value)
                status = ncrypt.NCryptSignHash(self._hKey, None, digest, len(digest), sig_buf, cbResult.value, ctypes.byref(cbResult), 0)
                
                if status != NCRYPT_SUCCESS:
                    raise RuntimeError(f"TPM Sign failed: {hex(status & 0xFFFFFFFF)}")
                
                # Convert raw (r, s) to DER
                raw_sig = sig_buf.raw[:cbResult.value]
                r = int.from_bytes(raw_sig[:32], 'big')
                s = int.from_bytes(raw_sig[32:], 'big')
                return encode_dss_signature(r, s)
                
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(f"TPM sign attempt {attempt+1} failed: {e}. Retrying...")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    raise

    def get_public_key(self) -> ec.EllipticCurvePublicKey:
        if not self._is_hardware:
            return self._private_key.public_key()
            
        # Export public key from TPM
        ncrypt = ctypes.windll.ncrypt
        BCRYPT_ECCPUBLIC_BLOB = "ECCPUBLICBLOB"
        NCRYPT_SUCCESS = 0
        
        cbResult = wintypes.DWORD(0)
        status = ncrypt.NCryptExportKey(self._hKey, 0, BCRYPT_ECCPUBLIC_BLOB, None, None, 0, ctypes.byref(cbResult), 0)
        if status != NCRYPT_SUCCESS:
            raise RuntimeError(f"TPM Export size failed: {hex(status & 0xFFFFFFFF)}")
            
        key_buf = ctypes.create_string_buffer(cbResult.value)
        status = ncrypt.NCryptExportKey(self._hKey, 0, BCRYPT_ECCPUBLIC_BLOB, None, key_buf, cbResult.value, ctypes.byref(cbResult), 0)
        if status != NCRYPT_SUCCESS:
            raise RuntimeError(f"TPM Export failed: {hex(status & 0xFFFFFFFF)}")
            
        # BCRYPT_ECCKEY_BLOB structure: 
        # Magic (4), cbKey (4), X (cbKey), Y (cbKey)
        # Magic for P256 Public is 0x31534345 (ECS1)
        raw_key = key_buf.raw[:cbResult.value]
        cbKey = int.from_bytes(raw_key[4:8], 'little')
        x = raw_key[8:8+cbKey]
        y = raw_key[8+cbKey:8+2*cbKey]
        
        # Reconstruct as cryptography public key
        # Point format: 0x04 + X + Y
        point_data = b"\x04" + x + y
        return ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), point_data)

    def get_status(self) -> dict:
        return {
            "type": "Windows TPM 2.0" if self._is_hardware else "Windows TPM (Simulated)",
            "available": True,
            "details": f"Key: {self.key_name}" + (" [Hardware]" if self._is_hardware else " [Fallback]")
        }

    def __del__(self):
        if hasattr(self, "_hKey") and self._hKey:
            ctypes.windll.ncrypt.NCryptFreeObject(self._hKey)
        if hasattr(self, "_hProv") and self._hProv:
            ctypes.windll.ncrypt.NCryptFreeObject(self._hProv)

class LegacyRawAnchor(SecureAnchor):
    """
    Adapter for raw private keys to fulfill the SecureAnchor interface.
    Used for backward compatibility with existing tests and legacy sessions.
    """
    def __init__(self, private_key: ed25519.Ed25519PrivateKey):
        self._private_key = private_key

    @property
    def algorithm(self) -> SigningAlgorithm:
        return SigningAlgorithm.ED25519

    def sign(self, data: bytes) -> bytes:
        return self._private_key.sign(data)

    def get_public_key(self) -> ed25519.Ed25519PublicKey:
        return self._private_key.public_key()

    def get_status(self) -> dict:
        return {
            "type": "Legacy Key",
            "available": True,
            "details": "In-memory raw private key"
        }
