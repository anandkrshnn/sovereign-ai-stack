"""Standalone Tamil Nadu evidence verifier.

Usage: python verify.py evidence.json [nonce] --trusted-keys trust.json --tenant tenant-id
This file intentionally imports only the standalone envelope module, not the
runner, policy, adapters, pipeline, or application internals.
"""

import argparse
import json
from pathlib import Path

from evidence_envelope import VerificationResult, WorkflowEvidenceEnvelope, verify_envelope


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify evidence against an out-of-band registry")
    parser.add_argument("evidence", type=Path)
    parser.add_argument("expected_nonce", nargs="?")
    parser.add_argument("--trusted-keys", type=Path, required=True)
    parser.add_argument("--tenant", required=True)
    args = parser.parse_args()
    try:
        envelope = WorkflowEvidenceEnvelope.model_validate_json(
            args.evidence.read_text(encoding="utf-8")
        )
        trust = json.loads(args.trusted_keys.read_text(encoding="utf-8"))
        if not isinstance(trust, dict) or not all(
            isinstance(tenant, str)
            and isinstance(keys, list)
            and all(isinstance(key, str) for key in keys)
            for tenant, keys in trust.items()
        ):
            raise ValueError("Trust registry must map tenants to lists of registered public keys")
        report = verify_envelope(
            envelope,
            args.expected_nonce,
            trusted_signers=trust,
            expected_tenant_id=args.tenant,
        )
    except (ValueError, json.JSONDecodeError, OSError):
        report = VerificationResult(
            valid=False,
            decision="invalid",
            run_id="",
            executed=None,
            policy_allowed=False,
        )
    print(json.dumps(dict(report), indent=2))
    return 0 if report.get("valid") else 1


if __name__ == "__main__":
    raise SystemExit(main())
