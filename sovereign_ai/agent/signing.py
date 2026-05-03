"""
Ed25519 forensic signing utilities for the Sovereign AI agent.

Provides non-repudiable payload signing using the cryptography library.
"""

import json
from pathlib import Path
from typing import Union


def sign_payload(payload: dict, private_key_path: Union[str, Path]) -> str:
    """Sign a JSON-serialised payload using an Ed25519 private key.

    Args:
        payload: A dictionary to be signed. It will be serialised to canonical
                 JSON (sorted keys, no extra whitespace) before signing.
        private_key_path: Path to a PEM-encoded Ed25519 private key file.

    Returns:
        A hex-encoded Ed25519 signature string.

    Raises:
        ImportError: If the ``cryptography`` package is not installed.
        FileNotFoundError: If the private key file does not exist.
        ValueError: If the key file does not contain a valid Ed25519 private key.
    """
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives.serialization import (
            load_pem_private_key,
        )
    except ImportError as exc:
        raise ImportError(
            "The 'cryptography' package is required for Ed25519 signing. "
            "Install it with: pip install cryptography"
        ) from exc

    key_path = Path(private_key_path)
    if not key_path.exists():
        raise FileNotFoundError(f"Private key file not found: {key_path}")

    pem_data = key_path.read_bytes()
    private_key = load_pem_private_key(pem_data, password=None)

    if not isinstance(private_key, Ed25519PrivateKey):
        raise ValueError(f"Key at {key_path} is not an Ed25519 private key.")

    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature_bytes = private_key.sign(canonical)
    return signature_bytes.hex()
