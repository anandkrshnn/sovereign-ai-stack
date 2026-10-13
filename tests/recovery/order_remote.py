"""Persistent fake order API. This database is remote state, never a gateway journal."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from uuid import uuid4

FIXTURE_TOKEN = "fixture-only-gateway-token"


def payload_digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


class FakeOrderAPI:
    def __init__(self, database: Path, *, deduplicate: bool, hold_response: bool = False):
        self.database = database
        self.deduplicate = deduplicate
        self.hold_response = hold_response
        self.committed = threading.Event()
        self.release_response = threading.Event()
        self.errors: list[str] = []
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE requests (
                    id INTEGER PRIMARY KEY, tenant TEXT, operation_key TEXT,
                    digest TEXT, authenticated INTEGER NOT NULL, order_id TEXT,
                    attempt_id TEXT, request_digest TEXT, owner_generation INTEGER
                );
                CREATE TABLE orders (
                    id TEXT PRIMARY KEY, tenant TEXT NOT NULL,
                    operation_key TEXT NOT NULL, digest TEXT NOT NULL
                );
                """)

        remote = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                if self.path != "/orders":
                    self.send_error(404)
                    return
                try:
                    length = int(self.headers["Content-Length"])
                    if not 0 < length <= 65536:
                        raise ValueError("invalid fixture body size")
                    body = json.loads(self.rfile.read(length))
                    execution = body.get("execution")
                    if execution is not None:
                        body = body["arguments"]
                        if (
                            execution["tenant_id"] != body["tenant_id"]
                            or execution["operation_key"] != body["operation_key"]
                            or execution["downstream_key"] != body["operation_key"]
                            or execution["tool_name"] != "orders.create"
                        ):
                            raise ValueError("unbound fixture attempt metadata")
                    authenticated = self.headers.get("Authorization") == f"Bearer {FIXTURE_TOKEN}"
                    with remote.connect() as db:
                        # Serialize fixture deduplication with request/effect persistence.
                        db.execute("BEGIN IMMEDIATE")
                        cursor = db.execute(
                            "INSERT INTO requests "
                            "(tenant,operation_key,digest,authenticated,attempt_id,"
                            "request_digest,owner_generation) VALUES (?,?,?,?,?,?,?)",
                            (
                                body["tenant_id"],
                                body["operation_key"],
                                body["payload_digest"],
                                int(authenticated),
                                execution["attempt_id"] if execution else None,
                                execution["request_digest"] if execution else None,
                                execution["owner_generation"] if execution else None,
                            ),
                        )
                        request_id = cursor.lastrowid
                        status = 401
                        receipt = {"error": "unauthorized"}
                        if authenticated:
                            if payload_digest(body["order"]) != body["payload_digest"]:
                                status, receipt = 400, {"error": "digest mismatch"}
                            else:
                                existing = None
                                if remote.deduplicate:
                                    existing = db.execute(
                                        "SELECT id,digest FROM orders "
                                        "WHERE tenant=? AND operation_key=?",
                                        (body["tenant_id"], body["operation_key"]),
                                    ).fetchone()
                                if existing and existing[1] != body["payload_digest"]:
                                    status, receipt = 409, {"error": "key conflict"}
                                else:
                                    order_id = existing[0] if existing else str(uuid4())
                                    if existing is None:
                                        db.execute(
                                            "INSERT INTO orders VALUES (?,?,?,?)",
                                            (
                                                order_id,
                                                body["tenant_id"],
                                                body["operation_key"],
                                                body["payload_digest"],
                                            ),
                                        )
                                    db.execute(
                                        "UPDATE requests SET order_id=? WHERE id=?",
                                        (order_id, request_id),
                                    )
                                    status = 201
                                    receipt = {
                                        "tenant_id": body["tenant_id"],
                                        "operation_key": body["operation_key"],
                                        "payload_digest": body["payload_digest"],
                                        "order_id": order_id,
                                    }
                                    if execution is not None:
                                        receipt.update(execution)
                    # Context-manager commit returned before this handshake.
                    if status == 201:
                        remote.committed.set()
                    if status == 201 and remote.hold_response:
                        if not remote.release_response.wait(60):
                            raise TimeoutError("fixture response-release watchdog expired")
                    encoded = json.dumps(receipt).encode()
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(encoded)))
                    self.end_headers()
                    self.wfile.write(encoded)
                except (BrokenPipeError, ConnectionResetError):
                    # Expected when a killed/timed-out worker loses its response.
                    pass
                except Exception as exc:
                    remote.errors.append(repr(exc))
                    self.close_connection = True

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.thread = threading.Thread(
            target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
        )

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=5)
        try:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA synchronous=FULL")
            assert db.execute("PRAGMA synchronous").fetchone()[0] == 2
            with db:
                yield db
        finally:
            db.close()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.server.server_port}/orders"

    def counts(self) -> dict:
        # Reopen the independent durable store; do not trust a worker's counters.
        with self.connect() as db:
            arrivals, authenticated = db.execute(
                "SELECT count(*),coalesce(sum(authenticated),0) FROM requests"
            ).fetchone()
            orders = db.execute("SELECT count(*) FROM orders").fetchone()[0]
        return {
            "arrivals": arrivals,
            "dispatches": authenticated,
            "unauthorized": arrivals - authenticated,
            "orders": orders,
            "duplicate_effects": max(0, orders - 1),
        }

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.release_response.set()
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()
