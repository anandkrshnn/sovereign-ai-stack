"""Opt-in, single-owner local SQLite execution journal; no reconciliation API."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from typing_extensions import Self

OperationKey = tuple[str, str, str]


class JournalError(RuntimeError):
    """Journal unavailable or a durable invariant could not be established."""


class JournalConflict(JournalError):
    """The scoped key was already bound to different immutable input."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class AttemptContext:
    tenant_id: str
    tool_name: str
    operation_key: str
    request_digest: str
    attempt_id: str
    owner_generation: int
    downstream_key: str

    @property
    def key(self) -> OperationKey:
        return self.tenant_id, self.tool_name, self.operation_key

    def validate_receipt(self, receipt: dict[str, Any]) -> None:
        """The trusted adapter must normalize an authoritative terminal receipt."""
        if any(
            type(receipt.get(name)) is not type(value) or receipt.get(name) != value
            for name, value in asdict(self).items()
        ):
            raise ValueError("remote_receipt_not_bound_to_dispatch_attempt")


@dataclass(frozen=True)
class JournalRecord:
    context: AttemptContext
    state: str
    output: dict[str, Any] | None
    evidence: dict[str, Any] | None


class SQLiteExecutionJournal:
    """One active process on a trusted local POSIX filesystem.

    An OS process lock is held for this object's entire lifetime. Startup may
    recover unfinished work only after obtaining that exclusive lock. A closed
    object cannot be used by a resumed caller. This is not distributed fencing,
    authenticated storage, power-loss validation, or provider reconciliation.
    """

    def __init__(self, path: str | Path):
        if os.name != "posix":
            raise JournalError("single_host_journal_requires_POSIX")
        import fcntl

        self._owner_pid = os.getpid()
        self.path = Path(path).resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self._mutex = RLock()
        self._closed = True
        self._lock_file = self.path.with_name(self.path.name + ".lock").open("a+b")
        os.chmod(self._lock_file.name, 0o600)
        try:
            fcntl.flock(self._lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self._lock_file.close()
            raise JournalError("another_journal_owner_is_active") from exc
        try:
            self._db = sqlite3.connect(
                self.path, timeout=5, isolation_level=None, check_same_thread=False
            )
            self._db.row_factory = sqlite3.Row
            os.chmod(self.path, 0o600)
            if self._db.execute("PRAGMA user_version").fetchone()[0] not in (0, 1):
                raise JournalError("unsupported_journal_schema_version")
            self._db.execute("PRAGMA foreign_keys=ON")
            self._db.execute("PRAGMA journal_mode=WAL")
            self._db.execute("PRAGMA synchronous=FULL")
            if self.durability_settings() != ("wal", 2):
                raise JournalError("WAL_FULL_readback_failed")
            self._db.executescript("""
                CREATE TABLE IF NOT EXISTS operations (
                    tenant TEXT NOT NULL, tool TEXT NOT NULL, operation_key TEXT NOT NULL,
                    request_digest TEXT NOT NULL, downstream_key TEXT NOT NULL,
                    attempt_id TEXT NOT NULL UNIQUE,
                    owner_generation INTEGER NOT NULL CHECK(owner_generation > 0),
                    state TEXT NOT NULL CHECK(state IN
                        ('reserved','in_flight','outcome_unknown','succeeded')),
                    PRIMARY KEY (tenant,tool,operation_key),
                    FOREIGN KEY (attempt_id) REFERENCES attempts(attempt_id)
                        DEFERRABLE INITIALLY DEFERRED
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    attempt_id TEXT PRIMARY KEY, tenant TEXT NOT NULL, tool TEXT NOT NULL,
                    operation_key TEXT NOT NULL, state TEXT NOT NULL,
                    output_json TEXT, evidence_json TEXT, error TEXT,
                    FOREIGN KEY (tenant,tool,operation_key)
                        REFERENCES operations(tenant,tool,operation_key)
                );
                CREATE TABLE IF NOT EXISTS transitions (
                    id INTEGER PRIMARY KEY, attempt_id TEXT NOT NULL,
                    owner_generation INTEGER NOT NULL, state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    FOREIGN KEY (attempt_id) REFERENCES attempts(attempt_id)
                );
                PRAGMA user_version=1;
                """)
            self._closed = False
            with self._transaction() as db:
                for row in db.execute(
                    "SELECT * FROM operations WHERE state IN ('reserved','in_flight')"
                ).fetchall():
                    context = self._context(row)
                    state = "outcome_unknown" if row["state"] == "in_flight" else "reserved"
                    generation = context.owner_generation + 1
                    db.execute(
                        "UPDATE operations SET state=?,owner_generation=? "
                        "WHERE tenant=? AND tool=? AND operation_key=?",
                        (state, generation, *context.key),
                    )
                    db.execute(
                        "UPDATE attempts SET state=?,error=? WHERE attempt_id=?",
                        (
                            state,
                            "process_interrupted" if state == "outcome_unknown" else None,
                            context.attempt_id,
                        ),
                    )
                    db.execute(
                        "INSERT INTO transitions VALUES (NULL,?,?,?,?)",
                        (context.attempt_id, generation, state, "exclusive_startup_recovery"),
                    )
        except BaseException:
            if hasattr(self, "_db"):
                self._db.close()
            self._closed = True
            self._lock_file.close()
            raise

    def durability_settings(self) -> tuple[str, int]:
        self._check_process()
        return (
            str(self._db.execute("PRAGMA journal_mode").fetchone()[0]),
            int(self._db.execute("PRAGMA synchronous").fetchone()[0]),
        )

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        self._check_process()
        with self._mutex:
            if self._closed:
                raise JournalError("journal_is_closed")
            self._db.execute("BEGIN IMMEDIATE")
            try:
                yield self._db
                self._db.execute("COMMIT")
            except BaseException:
                if self._db.in_transaction:
                    self._db.execute("ROLLBACK")
                raise

    def _check_process(self) -> None:
        if os.getpid() != self._owner_pid:
            raise JournalError("journal_cannot_be_inherited_across_processes")

    @staticmethod
    def _context(row: sqlite3.Row) -> AttemptContext:
        return AttemptContext(
            row["tenant"],
            row["tool"],
            row["operation_key"],
            row["request_digest"],
            row["attempt_id"],
            row["owner_generation"],
            row["downstream_key"],
        )

    def _record(self, db: sqlite3.Connection, key: OperationKey) -> JournalRecord | None:
        row = db.execute(
            "SELECT o.*,a.output_json,a.evidence_json FROM operations o "
            "JOIN attempts a ON a.attempt_id=o.attempt_id "
            "WHERE o.tenant=? AND o.tool=? AND o.operation_key=?",
            key,
        ).fetchone()
        if row is None:
            return None
        return JournalRecord(
            self._context(row),
            row["state"],
            json.loads(row["output_json"]) if row["output_json"] else None,
            json.loads(row["evidence_json"]) if row["evidence_json"] else None,
        )

    def get(self, key: OperationKey) -> JournalRecord | None:
        with self._transaction() as db:
            return self._record(db, key)

    def prepare(self, key: OperationKey, request_digest: str) -> JournalRecord:
        with self._transaction() as db:
            existing = self._record(db, key)
            if existing is not None:
                if existing.context.request_digest != request_digest:
                    raise JournalConflict("idempotency_input_conflict")
                return existing
            attempt_id = str(uuid4())
            db.execute(
                "INSERT INTO operations VALUES (?,?,?,?,?,?,?,?)",
                (*key, request_digest, key[2], attempt_id, 1, "reserved"),
            )
            db.execute(
                "INSERT INTO attempts VALUES (?,?,?,?,?,?,?,?)",
                (attempt_id, *key, "reserved", None, None, None),
            )
            db.execute(
                "INSERT INTO transitions VALUES (NULL,?,?,?,?)",
                (attempt_id, 1, "reserved", "operation_reserved"),
            )
            record = self._record(db, key)
            assert record is not None
            return record

    @staticmethod
    def _transition(db: sqlite3.Connection, context: AttemptContext, target: str) -> bool:
        expected = "reserved" if target == "in_flight" else "in_flight"
        cursor = db.execute(
            "UPDATE operations SET state=? WHERE tenant=? AND tool=? AND operation_key=? "
            "AND request_digest=? AND attempt_id=? AND owner_generation=? "
            "AND downstream_key=? AND state=?",
            (
                target,
                *context.key,
                context.request_digest,
                context.attempt_id,
                context.owner_generation,
                context.downstream_key,
                expected,
            ),
        )
        if cursor.rowcount != 1:
            return False
        changed = db.execute(
            "UPDATE attempts SET state=? WHERE attempt_id=? AND state=?",
            (target, context.attempt_id, expected),
        )
        if changed.rowcount != 1:
            raise JournalError("operation_attempt_state_conflict")
        return True

    def begin_dispatch(self, context: AttemptContext) -> bool:
        with self._transaction() as db:
            if not self._transition(db, context, "in_flight"):
                return False
            db.execute(
                "INSERT INTO transitions VALUES (NULL,?,?,?,?)",
                (context.attempt_id, context.owner_generation, "in_flight", "dispatch_authorized"),
            )
            return True  # The enclosing context commits before this return reaches the caller.

    @staticmethod
    def validate_confirmation(
        context: AttemptContext, output: dict[str, Any], evidence: dict[str, Any]
    ) -> None:
        context.validate_receipt(output)
        bindings = asdict(context)
        bindings.pop("downstream_key")
        if any(
            type(evidence.get(name)) is not type(value) or evidence.get(name) != value
            for name, value in bindings.items()
        ):
            raise ValueError("host_evidence_not_bound_to_dispatch_attempt")
        if (
            evidence.get("output_hash")
            != hashlib.sha256(canonical_json(output).encode()).hexdigest()
        ):
            raise ValueError("host_evidence_output_digest_mismatch")
        record_hash = hashlib.sha256(
            canonical_json({**evidence, "record_hash": None}).encode()
        ).hexdigest()
        if evidence.get("record_hash") != record_hash:
            raise ValueError("host_evidence_record_digest_mismatch")

    def complete(
        self, context: AttemptContext, output: dict[str, Any], evidence: dict[str, Any]
    ) -> bool:
        self.validate_confirmation(context, output, evidence)
        encoded_output, encoded_evidence = canonical_json(output), canonical_json(evidence)
        with self._transaction() as db:
            if not self._transition(db, context, "succeeded"):
                return False
            db.execute(
                "UPDATE attempts SET output_json=?,evidence_json=? WHERE attempt_id=?",
                (encoded_output, encoded_evidence, context.attempt_id),
            )
            db.execute(
                "INSERT INTO transitions VALUES (NULL,?,?,?,?)",
                (
                    context.attempt_id,
                    context.owner_generation,
                    "succeeded",
                    "bound_remote_response",
                ),
            )
            return True

    def mark_unknown(self, context: AttemptContext, reason: str) -> bool:
        with self._transaction() as db:
            if not self._transition(db, context, "outcome_unknown"):
                return False
            db.execute(
                "UPDATE attempts SET error=? WHERE attempt_id=?", (reason, context.attempt_id)
            )
            db.execute(
                "INSERT INTO transitions VALUES (NULL,?,?,?,?)",
                (context.attempt_id, context.owner_generation, "outcome_unknown", reason),
            )
            return True

    def close(self) -> None:
        self._check_process()
        with self._mutex:
            if not self._closed:
                self._closed = True
                self._db.close()
                self._lock_file.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
