# Trust-boundary regression contract

Tests-only follow-up to PR #2, based on commit
`111ca29bc1236312d2b02c97ba8f9b924493c735`.

Verified local baseline: **12 failed safety expectations, 8 passing controls**.
All failures are assertion failures, not import/collection errors. The run used
Python 3.13.11, Pydantic 2.14.1, cryptography 50.0.2, pytest 9.1.1, and
pytest-asyncio 1.4.0. Black, isort, Ruff, and compilation checks also passed.
Other Python versions, the complete application suite, and GitHub CI for this
new branch have not been validated by this local run.

These tests assert required safe behavior. They are deliberately **not**
marked `xfail` or skipped: the draft is expected to be red until implementation
changes meet the contract. Do not merge this tests-only branch without deciding
how to stage the corresponding fixes.

## Run without ML or TPM dependencies

From the repository root, with pytest, Pydantic 2, and cryptography installed:

```bash
python -m pytest -q --confcutdir=tests/security tests/security
```

`--confcutdir` excludes the parent `tests/conftest.py`, which eagerly imports
the full ML-backed package. The test fixture loads the real policy, runner,
envelope, schema, and workflow source under an isolated namespace. It bypasses
package initializers only; it does not replace enforcement or verification
logic. Module registrations are restored after each test.

Signing uses genuine local Ed25519 keys implementing the real `SecureAnchor`
interface. Adapters/webhooks are local fixtures. No model, government system,
external webhook, n8n service, HSM, or TPM is exercised.

## Required safety behavior

- Evidence with only a self-supplied public key must fail closed, even when its
  signature, hashes, and nonce are internally consistent. An externally trusted
  signer configuration and its positive acceptance tests still need an
  implementation/API decision; these tests do not invent that API.
- A changed or invalidly signed pending case-file request must not execute.
- An ambiguous write timeout must not be blindly retried or certified as
  non-execution. The fixture deliberately commits its effect before timing out.
  Without remote deduplication/reconciliation, propagate `TimeoutError`, or
  return an explicit unknown status with a non-boolean execution value.
  The generic orchestrator is separately tested against timeout-after-effect
  retries; its richer unknown-outcome evidence contract remains future work.
- Approval must remain bound to exact arguments, tool, and tenant when objects
  are replaced between approval and execution. Freezing a model alone is
  insufficient.
- Idempotency keys must be scoped by tenant and tool. Reusing a scoped key with
  a different input must reject, rather than reexecute or relabel cached output.
- Missing caller-supplied consequence metadata must not downgrade a write
  classified by a trusted host. `Step.consequence` is host-assigned in this
  fixture; arbitrary client fields are not automatically trusted in deployment.

Passing controls cover approval pauses, denied calls, single execution,
completed-run deduplication, result tampering, nonce mismatch, and independent
verification of a known fixture signature.

These are targeted unit-level regression contracts, not full application,
authenticated-host, restart durability, remote deduplication, or hardware
attestation tests. The existing LangChain constructor defect is outside this
tests-only trust-boundary scope.
