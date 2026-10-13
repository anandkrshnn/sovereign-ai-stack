# Order recovery: first three contracts

Opt-in journal implementation slice based on tests-only PR #6, commit
`d95b6a5ff289bfebaae5e3ffc8037076de7be62d`.
Owned implementation dependency: [issue #5](https://github.com/anandkrshnn/sovereign-ai-stack/issues/5),
assigned to `anandkrshnn`. The original red baseline remains recorded in
`RESULTS.md`; it is historical, not the implementation's current result.
Keep the implementation PR draft for review. Existing trust-regression
assertions, workflows, dependency declarations, and the root README are unchanged.

## Coverage

Three semantic cases, each run with fixture remote deduplication OFF and ON:

- **T20:** ordinary success, one authenticated dispatch and order, response
  association by tenant/key/payload digest, ordinary evidence-hook emission,
  and persisted attempt-bound response/evidence association.
- **T07:** remote SQLite commit returns, the response is held, the host worker
  receives SIGKILL, a new process submits the identical operation intent, and
  the expected state is unknown without another create dispatch.
- **T21:** a live worker's HTTP call times out after remote commit; the actual
  runner returns unknown without a retry, including a same-process submission
  of the same operation through a fresh run and normal host approval.

The actual `DeterministicOrchestrator` is instantiated normally with the
application's `SQLiteExecutionJournal` at the stable host-configured
`execution.sqlite` path. There is no replacement engine, fixture-only journal,
synthetic recovered outcome, or diagnostic-report reader driving execution.

The original assertions remain; additional assertions inspect the actual
application journal independently. T07 compares the attempt ID before death
and after recovery, checks one attempt total, and requires persisted unknown
without success evidence. Passing this slice does not satisfy all 27 Phase 1
cases, independent signer trust, or authoritative real-provider proof.

## Application journal boundary

The opt-in journal uses a trusted local POSIX filesystem and one active process:

- Startup obtains an exclusive process lock before changing recovery state.
  A second live owner fails rather than stealing a lease or marking live work
  interrupted.
  Journal objects also reject use by a forked child; a fresh process must obtain
  its own exclusive owner after the old host exits.
- WAL and FULL synchronous mode are enabled and read back. An unsupported
  schema version or failed durability setting rejects initialization.
- Scoped operation identity is `(tenant, tool, idempotency_key)`; a different
  request digest conflicts instead of creating another reservation.
- The immutable attempt ID and stable downstream key are stored before sending.
  Only a committed, generation-checked `reserved -> in_flight` transition permits
  adapter invocation. Transition history retains the dispatch generation.
- Exclusive startup recovery increments unfinished ownership generations.
  Reserved-only attempts remain reserved; interrupted in-flight attempts become
  unknown. No new attempt is created while unknown.
- Successful normalized remote responses and host evidence are persisted in one
  terminal transaction, bound to tenant/tool/key/digest/attempt/generation.
  Cached confirmation validates receipt association and evidence digests before
  reuse; a confirmed remote effect is not erased by semantic rejection.

`ToolAdapter.execute_attempt` receives frozen host metadata separately from the
unchanged caller-approved arguments. Only an attempt-aware adapter may dispatch
in journal mode. The fixture sends this metadata over HTTP and echoes it in the
receipt. Real adapters must establish their own documented authoritative
response association; a host-stamped dictionary alone is not remote proof.

There is no reconciliation, no-effect retry, replacement attempt, or late-evidence
reducer in this slice. Even `RetryableAdapterError` remains unknown in journal
mode because it is not attempt-bound terminal proof. `max_attempts` does not
override that rule. The legacy in-memory mode remains available and retains its
existing behavior, but does not acquire crash durability by default.

The external evidence hook is not atomically delivered with the SQLite commit;
the original durable receipt/evidence remains in the journal if hook delivery
fails. Approvals remain host-local and are rechecked normally on resubmission.
This is not distributed fencing, authenticated storage, a durable workflow
engine, or power-loss validation.

`test_execution_journal.py` adds focused unit/runner contracts, including
actual POSIX child SIGKILL before/after the barrier, exclusive ownership, stale
generations, concurrent claims, conflicts, receipt bindings, cached-evidence
corruption, unsupported adapters, approval binding, and simulated storage
failures. Mock-receipt tests are not HTTP or provider evidence; the six separate
HTTP configurations still use fresh ordinary-import worker processes.

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

Use a POSIX/Linux Python environment with the repository's declared dependencies.
From the repository root, create a virtual environment and install the relevant
existing extras (no TPM extra is needed for this fixture):

```sh
python -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[verify,bridge,agent,dev]'
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
```

Torch is declared in `verify`; the core `sentence-transformers` dependency brings
its ML prerequisites. Wheel availability, CPU/GPU selection, and package versions
depend on the platform. This setup describes declared dependencies, not a
verified fresh installation on every supported Python version.

Run:

```sh
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" python -m pytest \
  tests/recovery/test_order_recovery_slice.py -q -s

PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" python -m pytest \
  'tests/recovery/test_order_recovery_slice.py::test_T07_held_response_SIGKILL_restart[dedupe-off]' \
  -q -s

PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" python -m pytest \
  tests/recovery/test_execution_journal.py -q
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
