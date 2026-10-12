# Initial recovery slice: observed local results

Application baseline: PR #4 at
`31c3786723df049a320f6fc3c3b7fa2e03ce6088`.
Local recovery suite timestamp: 2026-10-12 17:23:59 UTC.
This is a local test report, not GitHub CI, production, or real-provider evidence.

## Completed execution

Normal pytest collection and ordinary package imports were used. The host
worker uses the existing repository orchestrator, a test HTTP adapter, and
an independently persistent loopback fake order API. No package initializer,
policy, approval, or execution implementation is replaced in these new tests.

**Six configurations: four passed, two failed, zero errors/skips.**
Recovery suite duration: 183.84 seconds. Exit status: 1.

| Case | Fixture deduplication | Dispatches | Orders | Outcome observed | Result |
| --- | --- | ---: | ---: | --- | --- |
| T20 normal success | OFF | 1 | 1 | succeeded | PASS |
| T20 normal success | ON | 1 | 1 | succeeded | PASS |
| T07 SIGKILL + restart | OFF | 2 | 2 | succeeded after restart | FAIL |
| T07 SIGKILL + restart | ON | 2 | 1 | succeeded after restart | FAIL |
| T21 live timeout | OFF | 1 | 1 | outcome_unknown, including in-process resubmission | PASS |
| T21 live timeout | ON | 1 | 1 | outcome_unknown, including in-process resubmission | PASS |

Before either T07 kill, one authenticated request and one remote order were
persisted. SIGKILL's return code was verified as -9; a fresh process then
submitted the same stored caller intent. No reconciliation lookup occurred.
The required post-restart observation was one dispatch, one order, and
outcome_unknown without a receipt/evidence bundle for a new execution.

Instead, both modes received a second create dispatch. OFF produced one
duplicate order effect. ON hid that duplicate effect by reusing the remote
order but still exposed the forbidden additional dispatch. These are actual
assertion failures after remote effects and process death, not missing-import
failures or fake expected-failure annotations.

The results are consistent with the inspected runner's process-local execution
dictionary. This experiment establishes the failure in these local conditions;
it does not establish real-provider behavior or a universal failure rate.

## Existing targeted regressions

The unchanged targeted suite completed **62 passed**, zero errors/skips/failures:

- 34 security contracts/controls.
- 3 orchestration tests.
- 23 case-file workflow tests.
- 2 workflow CLI tests.

Command:

```sh
PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}" \
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python -m pytest \
  tests/security tests/orchestration/test_runner.py \
  tests/workflows/test_tamilnadu_cli.py \
  tests/workflows/test_tamilnadu_seva.py -q
```

Normal root collection applied. Existing security tests retain their unchanged
private-namespace/module-loading fixtures; do not describe those 34 tests as
full application integration. The six new recovery configurations do not use
those fixture loaders. No full application suite or hardware validation ran.

## Static checks and environment

Black, isort, Ruff, Python compilation, and whitespace checks passed for the
new files. Targeted mypy passed for the three helper modules with
`--follow-imports=skip --check-untyped-defs --ignore-missing-imports`;
this is not full-project type verification.

Local host: Linux/POSIX x86_64, Python 3.13.11.
Import prerequisites included Torch 2.14.1+cpu, Transformers 5.19.0,
NumPy 2.5.4, and SciPy 1.18.1. These were installed in the conversation's
execution environment, not added to repository dependency files.
No model was instantiated or downloaded.

An initial collection attempt lacked Torch; that blocker was resolved without
bypassing imports. An earlier 180-second shell run timed out before all cases
completed and is not counted as a completed suite. The complete run above
used the actual pytest and worker watchdogs without an aggregate shell cutoff.

## Meaning and limits

T20 verifies initial response association and evidence-hook emission, not
persisted attempt-bound evidence or the complete durable success contract.
T21 verifies live-process ambiguity handling, not restart durability.
The actual journal must be implemented and explicitly wired into the worker;
reading the controller's diagnostic output as a recovery journal is forbidden.

Implementation remains tracked in [issue #5](https://github.com/anandkrshnn/sovereign-ai-stack/issues/5).
Keep the tests-only PR draft until that dependency and these failures are
resolved. This report does not close the 27-case Phase 1 gate or the real-API
milestone. No 1,000-trial campaign, customer outreach, real API call,
production merge, or deployment ran.
