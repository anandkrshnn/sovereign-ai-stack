# Order recovery: first three contracts

Tests-only slice based on PR #4, commit
`31c3786723df049a320f6fc3c3b7fa2e03ce6088`.
Owned implementation dependency: [issue #5](https://github.com/anandkrshnn/sovereign-ai-stack/issues/5),
assigned to `anandkrshnn`. Keep this PR draft while the restart contract is red.
No production runtime, existing tests, workflow, or dependency files are changed.

## Coverage

Three semantic cases, each run with fixture remote deduplication OFF and ON:

- **T20:** ordinary success, one authenticated dispatch and order, response
  association by tenant/key/payload digest, and ordinary evidence-hook emission.
- **T07:** remote SQLite commit returns, the response is held, the host worker
  receives SIGKILL, a new process submits the identical operation intent, and
  the expected state is unknown without another create dispatch.
- **T21:** a live worker's HTTP call times out after remote commit; the actual
  runner returns unknown without a retry, including a same-process submission
  of the same operation through a fresh run and normal host approval.

The existing `DeterministicOrchestrator` is instantiated normally in the host
worker. There is no replacement execution engine or fixture-only journal.
When the real journal is implemented, its explicit persistent configuration
must be wired into this worker's constructor; a synthetic recovery state or
a report-reader shortcut would invalidate the test.

T20 is an initial response/evidence control, not proof of persisted
attempt-bound evidence or the complete durable success contract. T07 must stay
red until the real runtime is wired and satisfies restart safety. Passing these
controls alone does not satisfy all 27 Phase 1 cases.

## Harness boundaries

`order_remote.py` serves a loopback HTTP API using a separate persistent SQLite
database (WAL, FULL synchronous mode). It records authenticated arrivals
independently from created orders. Deduplication OFF has no order-key uniqueness
constraint; ON can hide duplicate effects, but cannot hide extra dispatches.

The remote commit event is set only after the transaction context commits.
The controller checks one persisted dispatch/effect before killing the original
worker, verifies SIGKILL's exit code, then releases the held response. The API
stays alive while the host worker restarts; no lookup/reconciliation is invoked
in T07, so unknown must be preserved before reconciliation.

The controller persists only caller intent/identities and diagnostic results.
Workers never read previous diagnostic results, remote SQLite tables, or
controller counters to decide execution outcomes. The fake API's database is
not a gateway execution ledger. A repeated host approval does not authorize
replaying an already ambiguous operation.

The adapter is a test-specific host HTTP connector, with no transport retry
loop, and a public fixture-only token. These tests do not prove production
credential isolation (T22), host principal authentication, signer trust,
authoritative real-provider evidence, or normal-import success on every host.
No real API, model construction/download, trial, or prospect demo is involved.
The host has only one worker process for this slice; killing it terminates its
runner and adapter, not an imagined separate gateway process.

## Run and replay

Use a supported POSIX/Linux Python environment with the repository's declared
dependencies. From the repository root:

```sh
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" python -m pytest \
  tests/recovery/test_order_recovery_slice.py -q -s

PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" python -m pytest \
  'tests/recovery/test_order_recovery_slice.py::test_T07_held_response_SIGKILL_restart[dedupe-off]' \
  -q -s
```

Normal `tests/conftest.py` and package imports apply. Missing Torch/Transformers
or other import prerequisites are collection/environment blockers, not six
passing tests or an expected behavioral failure. Do not use `--noconftest`,
`--confcutdir`, fake `sys.modules`, or root-package bypass loaders to get green.
Offline flags prevent model downloads; the worker does not instantiate an NLI
model. They do not bypass required Python imports.

The watchdogs limit hangs; the commit event, not a sleep, establishes fault
ordering. A missing commit handshake or crashed fixture is a harness failure,
not a successful recovery observation. Diagnostic logs/results and crash
observations remain under pytest's temporary directory.

## Deferred within the same gate

After this slice, add T06, T05, and T22, then the remaining Phase 1 contracts.
T26's compatible evidence variant is a repeated terminal rejection for attempt
N concurrent with positive evidence for N+1. A late success for the previously
terminal-no-effect N is the contradiction variant. T25's permitted-retry portion
shares T14's no-effect capability prerequisite; it is not independent provider
retry coverage.

The local fake supports the declared fixture behavior only. A real provider
uses native deduplication and the predeclared supported capability matrix.
Phase 2 can wait for an explicitly authorized partner sandbox; that access
dependency is not a failed local recovery test. No real-API milestone is passed
by this slice.

Until one crash-recovery path passes its tests for one real API, everything
that does not serve that gets deferred.
