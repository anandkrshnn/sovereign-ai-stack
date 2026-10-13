"""Finite in-process sequence checks, not SIGKILL or real-provider evidence."""

from dataclasses import asdict, replace
from hashlib import sha256
from pathlib import Path
from sqlite3 import Row, connect
from tempfile import TemporaryDirectory

import pytest
from hypothesis import note, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule
from test_execution_journal import KEY, fixture_runner, submit

from sovereign_ai.orchestration import (
    JournalConflict,
    JournalError,
    RunState,
    SQLiteExecutionJournal,
)
from sovereign_ai.orchestration.adapters import ToolAdapter
from sovereign_ai.orchestration.journal import canonical_json

ARGUMENTS = {"sku": "fixture"}
REQUEST_DIGEST = sha256(
    canonical_json(
        {"arguments": ARGUMENTS, "host_consequence": "write", "policy_consequence": "write"}
    ).encode()
).hexdigest()
OUTCOMES = st.sampled_from(["success", "lost-response", "unbound-receipt"])


class ObservedAdapter(ToolAdapter):
    """An in-process mock ledger that survives journal close/reopen actions."""

    name = KEY[1]

    def __init__(self, owner):
        self.owner = owner
        self.calls = []
        self.outcome = "success"

    def execute(self, *_args):
        raise AssertionError("sequence runner bypassed the attempt-aware entry point")

    def execute_attempt(self, arguments, _timeout_seconds, context):
        record = self.owner.journal.get(KEY)
        assert record is not None and record.state == "in_flight"
        assert record.context == context, "adapter invoked without the committed current barrier"
        assert arguments == ARGUMENTS
        self.calls.append(asdict(context))
        if self.outcome == "lost-response":
            raise TimeoutError("injected mock response loss")
        receipt = {**asdict(context), "order_id": "mock-order"}
        if self.outcome == "unbound-receipt":
            receipt["attempt_id"] = "not-the-authorized-attempt"
        return receipt


class JournalSequences(RuleBasedStateMachine):
    """One scoped operation; no retries, reconciliation, or simulated takeover."""

    def __init__(self):
        super().__init__()
        self.directory = TemporaryDirectory(prefix="journal-sequence-")
        self.path = Path(self.directory.name) / "execution.sqlite"
        self.journal = SQLiteExecutionJournal(self.path)
        self.adapter = ObservedAdapter(self)
        # Expected state advances from commands, never from a database observation.
        self.state = "empty"
        self.generation = 0
        self.attempt_id = None
        self.authorizations = 0
        self.expected_calls = 0
        self.contexts = []
        self.trace = []

    def log(self, action, **details):
        self.trace.append({"action": action, "before": self.state, **details})

    def capture_identity(self):
        record = self.journal.get(KEY)
        assert record is not None, self.trace
        if self.attempt_id is None:
            self.attempt_id = record.context.attempt_id
        assert record.context.attempt_id == self.attempt_id, self.trace
        self.contexts.append(record.context)
        return record.context

    @rule()
    def reserve(self):
        self.log("reserve")
        self.journal.prepare(KEY, REQUEST_DIGEST)
        if self.state == "empty":
            self.state, self.generation = "reserved", 1
        self.capture_identity()

    @precondition(lambda self: self.state != "empty")
    @rule()
    def conflicting_digest(self):
        self.log("conflicting_digest")
        with pytest.raises(JournalConflict):
            self.journal.prepare(KEY, "b" * 64)

    @precondition(lambda self: self.state != "empty")
    @rule()
    def authorize_current_context(self):
        self.log("authorize_current_context")
        expected = self.state == "reserved"
        permitted = self.journal.begin_dispatch(self.journal.get(KEY).context)
        assert permitted is expected, self.trace
        if expected:
            self.state = "in_flight"
            self.authorizations += 1

    @precondition(lambda self: bool(self.contexts))
    @rule(index=st.integers(min_value=0, max_value=50))
    def try_retained_context(self, index):
        context = self.contexts[index % len(self.contexts)]
        self.log("try_retained_context", generation=context.owner_generation)
        expected = self.state == "reserved" and context.owner_generation == self.generation
        permitted = self.journal.begin_dispatch(context)
        assert permitted is expected, self.trace
        if expected:
            self.state = "in_flight"
            self.authorizations += 1

    @precondition(lambda self: self.state != "empty")
    @rule(
        field=st.sampled_from(
            [
                "tenant_id",
                "tool_name",
                "operation_key",
                "request_digest",
                "attempt_id",
                "owner_generation",
                "downstream_key",
            ]
        )
    )
    def reject_tampered_context(self, field):
        context = self.journal.get(KEY).context
        changed = (
            context.owner_generation + 1
            if field == "owner_generation"
            else f"not-{getattr(context, field)}"
        )
        self.log("reject_tampered_context", field=field)
        assert not self.journal.begin_dispatch(replace(context, **{field: changed})), self.trace

    @precondition(lambda self: self.state == "in_flight")
    @rule()
    def abandon_authorized_attempt(self):
        self.log("abandon_authorized_attempt")
        assert self.journal.mark_unknown(
            self.journal.get(KEY).context, "injected sequence interruption"
        ), self.trace
        self.state = "outcome_unknown"

    @precondition(lambda self: self.state == "outcome_unknown")
    @rule(index=st.integers(min_value=0, max_value=50))
    def reject_late_mock_completion(self, index):
        """The current slice has no reducer that may resolve unknown."""
        context = self.contexts[index % len(self.contexts)]
        self.log("reject_late_mock_completion", generation=context.owner_generation)
        output = {**asdict(context), "order_id": "late-mock-order"}
        bindings = asdict(context)
        bindings.pop("downstream_key")
        evidence = {
            **bindings,
            "output_hash": sha256(canonical_json(output).encode()).hexdigest(),
            "record_hash": None,
        }
        evidence["record_hash"] = sha256(canonical_json(evidence).encode()).hexdigest()
        assert not self.journal.complete(context, output, evidence), self.trace

    @rule()
    def reopen_owner(self):
        self.log("reopen_owner")
        self.journal.close()
        self.journal = SQLiteExecutionJournal(self.path)
        if self.state in {"reserved", "in_flight"}:
            self.generation += 1
        if self.state == "in_flight":
            self.state = "outcome_unknown"
        if self.state != "empty":
            self.capture_identity()

    @rule()
    def exclude_live_second_owner(self):
        self.log("exclude_live_second_owner")
        with pytest.raises(JournalError, match="another_journal_owner"):
            SQLiteExecutionJournal(self.path)

    @rule(outcome=OUTCOMES)
    def submit_through_runner(self, outcome):
        self.log("submit_through_runner", outcome=outcome)
        prior = self.state
        self.adapter.outcome = outcome
        runner, events, task, step = fixture_runner(self.journal, self.adapter)
        step.consequence = "write"
        result = submit(runner, events, task, step)
        if prior in {"empty", "reserved"}:
            self.authorizations += 1
            self.expected_calls += 1
            if prior == "empty":
                self.generation = 1
            self.state = "succeeded" if outcome == "success" else "outcome_unknown"
        elif prior == "in_flight":
            # The runner preserves the already authorized ambiguous attempt.
            self.state = "in_flight"
        expected_run = RunState.SUCCEEDED if self.state == "succeeded" else RunState.OUTCOME_UNKNOWN
        assert result.state is expected_run, self.trace
        assert result.attempts == int(prior in {"empty", "reserved"}), self.trace
        self.capture_identity()

    def check_model(self):
        """Independent persisted-state and call-count oracle, also used by fixed traces."""
        assert self.authorizations <= 1, self.trace
        assert len(self.adapter.calls) == self.expected_calls <= self.authorizations, self.trace
        with connect(f"file:{self.path}?mode=ro", uri=True) as db:
            db.row_factory = Row
            operations = db.execute("SELECT * FROM operations").fetchall()
            attempts = db.execute("SELECT attempt_id,state,output_json,evidence_json FROM attempts")
            attempts = attempts.fetchall()
            authorizations = db.execute(
                "SELECT count(*) FROM transitions WHERE reason='dispatch_authorized'"
            ).fetchone()[0]
        assert authorizations == self.authorizations, self.trace
        if self.state == "empty":
            assert operations == attempts == [], self.trace
            return
        assert len(operations) == len(attempts) == 1, self.trace
        persisted = operations[0]
        assert persisted["state"] == self.state, self.trace
        assert persisted["owner_generation"] == self.generation, self.trace
        assert persisted["attempt_id"] == self.attempt_id, self.trace
        assert (persisted["tenant"], persisted["tool"], persisted["operation_key"]) == KEY
        assert persisted["request_digest"] == REQUEST_DIGEST, self.trace
        assert persisted["downstream_key"] == KEY[2], self.trace
        record = self.journal.get(KEY)
        assert record.state == self.state, self.trace
        assert record.context.owner_generation == self.generation, self.trace
        assert record.context.attempt_id == attempts[0][0] == self.attempt_id, self.trace
        assert attempts[0][1] == self.state, self.trace
        assert record.context.key == KEY, self.trace
        assert record.context.downstream_key == KEY[2], self.trace
        assert record.context.request_digest == REQUEST_DIGEST, self.trace
        if self.state == "succeeded":
            assert self.expected_calls == 1, self.trace
            assert record.output["attempt_id"] == record.evidence["attempt_id"] == self.attempt_id
            assert record.evidence["owner_generation"] == self.generation, self.trace
            SQLiteExecutionJournal.validate_confirmation(
                record.context, record.output, record.evidence
            )
        else:
            assert record.output is record.evidence is None, self.trace

    @invariant()
    def persisted_state_matches_independent_model(self):
        note(f"action trace: {self.trace!r}")
        self.check_model()

    def teardown(self):
        try:
            self.journal.close()
        finally:
            self.directory.cleanup()


TestJournalSequences = JournalSequences.TestCase
TestJournalSequences.settings = settings(
    max_examples=50,
    stateful_step_count=20,
    deadline=None,
    database=None,
    derandomize=True,
    print_blob=True,
)


@pytest.mark.parametrize(
    "after_barrier", [False, True], ids=["reserved-reopen", "in-flight-reopen"]
)
def test_fixed_recovery_sequence(after_barrier):
    """Keep critical boundaries covered regardless of generated rule selection."""
    machine = JournalSequences()
    try:
        machine.reserve()
        original = machine.contexts[0]
        if after_barrier:
            machine.authorize_current_context()
        machine.reopen_owner()
        assert machine.journal.get(KEY).context.owner_generation == original.owner_generation + 1
        machine.try_retained_context(index=0)
        machine.check_model()
        machine.submit_through_runner(outcome="success")
        machine.check_model()
        machine.reopen_owner()
        machine.submit_through_runner(outcome="success")
        machine.check_model()
        assert machine.state == ("outcome_unknown" if after_barrier else "succeeded")
        assert len(machine.adapter.calls) == (0 if after_barrier else 1)
    finally:
        machine.teardown()


def test_oracle_detects_injected_repeat_authorization(monkeypatch):
    """Sensitivity check: this is an intentionally unsafe test-only mutation."""
    machine = JournalSequences()
    try:
        machine.reserve()
        machine.authorize_current_context()
        monkeypatch.setattr(machine.journal, "begin_dispatch", lambda _context: True)
        with pytest.raises(AssertionError):
            machine.authorize_current_context()
    finally:
        machine.teardown()


def test_adapter_observer_detects_missing_committed_barrier(monkeypatch):
    machine = JournalSequences()
    try:
        # Pretend the barrier succeeded without committing it. Production code
        # is untouched; the adapter observer and model must reject this behavior.
        monkeypatch.setattr(machine.journal, "begin_dispatch", lambda _context: True)
        with pytest.raises(AssertionError):
            machine.submit_through_runner(outcome="success")
        assert not machine.adapter.calls
    finally:
        machine.teardown()
