"""Load real boundary modules without model downloads or hardware initialization.

Only package initializers are bypassed. Policy, approval, execution, hashing,
schema validation, and envelope verification all use the repository's source.
All module registrations are restored by pytest's monkeypatch fixture.
"""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519


@pytest.fixture
def subject(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    prefix = f"_sovereign_security_{uuid4().hex}"

    def namespace(name, path):
        module = ModuleType(name)
        module.__path__ = [str(path)]
        monkeypatch.setitem(sys.modules, name, module)
        return module

    def load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        return module

    namespace(prefix, root / "sovereign_ai")
    namespace(f"{prefix}.common", root / "sovereign_ai/common")
    hardware = namespace(
        f"{prefix}.common.hardware_trust", root / "sovereign_ai/common/hardware_trust"
    )
    namespace(f"{prefix}.orchestration", root / "sovereign_ai/orchestration")
    namespace(f"{prefix}.workflows", root / "sovereign_ai/workflows")
    schemas = load(f"{prefix}.common.schemas", root / "sovereign_ai/common/schemas.py")
    base = load(
        f"{prefix}.common.hardware_trust.base", root / "sovereign_ai/common/hardware_trust/base.py"
    )
    hardware.SecureAnchor = base.SecureAnchor
    envelope = load("evidence_envelope", root / "evidence_envelope.py")
    models = load(f"{prefix}.orchestration.models", root / "sovereign_ai/orchestration/models.py")
    adapters = load(
        f"{prefix}.orchestration.adapters", root / "sovereign_ai/orchestration/adapters.py"
    )
    policy = load(f"{prefix}.orchestration.policy", root / "sovereign_ai/orchestration/policy.py")
    runner = load(f"{prefix}.orchestration.runner", root / "sovereign_ai/orchestration/runner.py")
    workflow = load(
        f"{prefix}.workflows.tamilnadu_seva", root / "sovereign_ai/workflows/tamilnadu_seva.py"
    )
    return SimpleNamespace(
        envelope=envelope,
        models=models,
        adapters=adapters,
        policy=policy,
        runner=runner,
        workflow=workflow,
        schemas=schemas,
        anchor_base=base.SecureAnchor,
    )


@pytest.fixture
def anchor_factory(subject):
    class LocalAnchor(subject.anchor_base):
        """Real Ed25519 signing fixture; deliberately not a hardware anchor."""

        def __init__(self):
            self.key = ed25519.Ed25519PrivateKey.generate()

        def sign_payload(self, payload):
            return self.key.sign(payload)

        def get_public_key(self):
            return self.key.public_key()

        def get_public_key_pem(self):
            return self.get_public_key().public_bytes(
                serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
            )

        def get_signing_algorithm(self):
            return subject.schemas.SigningAlgorithm.ED25519

        @property
        def is_hardware(self):
            return False

        def generate_quote(self, nonce, pcrs):
            raise NotImplementedError("This fixture does not simulate hardware attestation")

        def seal_key(self, plaintext_key):
            raise NotImplementedError("Hardware sealing is outside these unit tests")

        def unseal_key(self, sealed_key):
            raise NotImplementedError("Hardware sealing is outside these unit tests")

    return LocalAnchor
