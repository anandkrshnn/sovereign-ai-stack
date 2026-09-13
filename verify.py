"""Standalone Tamil Nadu evidence verifier.

Usage: python verify.py evidence.json [nonce]
This file intentionally imports only the standalone envelope module, not the
runner, policy, adapters, pipeline, or application internals.
"""

import json
import sys
from pathlib import Path

from evidence_envelope import WorkflowEvidenceEnvelope, verify_envelope


def main() -> int:
    if len(sys.argv) not in {2, 3}:
        print("usage: python verify.py evidence.json [expected_nonce]", file=sys.stderr)
        return 2
    envelope = WorkflowEvidenceEnvelope.model_validate_json(Path(sys.argv[1]).read_text())
    valid = verify_envelope(envelope, sys.argv[2] if len(sys.argv) == 3 else None)
    print(json.dumps({"valid": valid, "run_id": str(envelope.run_id)}))
    return 0 if valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
