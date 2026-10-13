# First local journal implementation: observed results

Implementation parent: tests-only PR #6 at
`d95b6a5ff289bfebaae5e3ffc8037076de7be62d`.
Final local suite timestamp: 2026-10-13 02:47:05 UTC.
`RESULTS.md` remains the unchanged historical red baseline.

## Final-source execution

**95 passed, zero failures/errors/skips**, in 144.39 seconds; exit status 0:

- 6 HTTP recovery configurations: T20, T07, T21, each with deduplication OFF/ON.
- 27 focused journal/runner configurations, including actual POSIX child kills,
  concurrent claims, stale generations, inherited-connection rejection,
  receipt bindings, and simulated storage failures.
- 62 unchanged targeted security/orchestration/workflow/CLI regressions.

The 27 focused configurations are **not** the frozen 27-case Phase 1 gate.
This slice exercises three named HTTP contracts, not the entire gate.
The direct journal child-kill controls are not full end-to-end T05/T06 acceptance.

| HTTP case | Remote deduplication | Dispatches | Orders | Returned state |
| --- | --- | ---: | ---: | --- |
| T20 normal success | OFF | 1 | 1 | succeeded |
| T20 normal success | ON | 1 | 1 | succeeded |
| T07 held response / SIGKILL / restart | OFF | 1 | 1 | outcome_unknown |
| T07 held response / SIGKILL / restart | ON | 1 | 1 | outcome_unknown |
| T21 live timeout and in-process resubmission | OFF | 1 | 1 | outcome_unknown |
| T21 live timeout and in-process resubmission | ON | 1 | 1 | outcome_unknown |

Both T07 workers were killed with verified SIGKILL exit code -9 and restarted
as distinct processes. The original assertions were retained and strengthened:
the application journal was in-flight before death, unknown after recovery,
held the same attempt ID and exactly one attempt, and had no success evidence.
The remote remained alive and persisted independently from the host journal.

Read-only inspection of both final T07 databases additionally confirmed:

- One remote request whose attempt ID and request digest matched the journal.
- Dispatch generation 1, recovered ownership generation 2.
- Transition history: reserved/generation 1, in_flight/generation 1,
  outcome_unknown/generation 2.

Deduplication OFF now stays at one order rather than the baseline's two.
Deduplication ON also stays at one dispatch rather than merely hiding a second
dispatch. No reconciliation lookup or inferred no-effect outcome was used.
T20 persisted response/evidence attempt association; T21 made one attempt despite
the manifest permitting up to three.

## Reproduce

From the repository root after the setup in `README.md`:

```sh
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m pytest \
  tests/recovery tests/security tests/orchestration/test_runner.py \
  tests/workflows/test_tamilnadu_cli.py \
  tests/workflows/test_tamilnadu_seva.py -q -s --durations=10
```

Normal root collection and ordinary package imports applied. The HTTP workers
start fresh Python processes; no root initializer or implementation bypass is
installed. Existing security fixtures retain their unchanged private-namespace
module loaders, so the 34 security tests are not full application integration.
An earlier implementation iteration completed 94 passes; the 95-case result
above is the final code with the process-identity guard and its additional test.

## Static checks and environment

Black/isort/Ruff passed for the ten changed/new Python files. Compilation and
whitespace checks passed. Targeted mypy passed for eight runtime/helper modules
with `--follow-imports=skip --check-untyped-defs --ignore-missing-imports`.
This is not full-project typing. A broader orchestration-directory Ruff probe
also found the pre-existing unused import in unchanged `evidence.py`; it was not
silently fixed or counted as clean full-directory lint.

Verified local environment:

- Linux/POSIX, Python 3.13.11, SQLite 3.51.1, pytest 9.1.1.
- Pydantic 2.14.1, Torch 2.14.1+cpu, Transformers 5.19.0.
- NumPy 2.5.4 and SciPy 1.18.1.

No model was instantiated/downloaded. No dependency declaration or workflow
changed. The documented extras install command was not independently tested
in a new environment on every supported Python version.

## Remaining boundary

The journal is opt-in and requires one active owner on a trusted local POSIX
filesystem. WAL/FULL read-back and process death were tested; power loss,
network/shared filesystems, distributed failover, arbitrary database writers,
independent storage authentication, and production hardware were not.
The default in-memory path remains volatile.

Normalized fake receipts carry attempt metadata. That is useful association
evidence under the fixture's conditions, not validation of a real provider's
authentication, idempotency, fencing, or terminal-outcome semantics. Principal
authentication is still supplied by the host.

No reconciliation, replacement attempts, safe no-effect retry, late-evidence
reducer, durable approval store, real API operation, full application suite,
randomized campaign, merge, or deployment ran. External evidence-hook delivery
is not atomic with the SQLite terminal commit.

[Issue #5](https://github.com/anandkrshnn/sovereign-ai-stack/issues/5) stays open.
The real-API milestone and the remaining Phase 1 contracts are not satisfied by
this local result.
