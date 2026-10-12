"""Subprocess controller; persists caller intent, not execution outcomes."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, TextIO, TypedDict
from uuid import uuid4

from order_remote import FIXTURE_TOKEN, payload_digest

ROOT = Path(__file__).resolve().parents[2]


class Worker(TypedDict):
    process: subprocess.Popen[bytes]
    report: Path
    log: Path


class OrderController:
    def __init__(self, directory: Path, url: str):
        self.directory = directory
        self.url = url
        self.workers: list[Worker] = []
        self.streams: list[TextIO] = []
        self.manifest = directory / "caller-intent.json"
        payload = {"sku": "fixture-sku", "quantity": 1}
        self.arguments = {
            "tenant_id": "fixture-tenant",
            "operation_key": str(uuid4()),
            "payload_digest": payload_digest(payload),
            "order": payload,
        }
        task_id = str(uuid4())
        self.manifest.write_text(
            json.dumps(
                {
                    "task": {
                        "id": task_id,
                        "tenant_id": "fixture-tenant",
                        "agent_id": str(uuid4()),
                        "idempotency_key": "fixture-task",
                    },
                    "run_id": str(uuid4()),
                    "step": {
                        "id": str(uuid4()),
                        "name": "create fixture order",
                        "consequence": "write",
                        "tool_call": {
                            "id": str(uuid4()),
                            "tool_name": "orders.create",
                            "arguments": self.arguments,
                            "idempotency_key": self.arguments["operation_key"],
                            "max_attempts": 3,
                        },
                    },
                }
            )
        )

    def start(self, *, timeout: float = 5, repeat: bool = False) -> Worker:
        index = len(self.workers)
        report = self.directory / f"worker-{index}.json"
        log = self.directory / f"worker-{index}.log"
        stream = log.open("w")
        self.streams.append(stream)
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join(
            part for part in (str(ROOT), env.get("PYTHONPATH", "")) if part
        )
        env["ORDER_TEST_GATEWAY_TOKEN"] = FIXTURE_TOKEN
        env["HF_HUB_OFFLINE"] = "1"
        env["TRANSFORMERS_OFFLINE"] = "1"
        command = [
            sys.executable,
            str(Path(__file__).with_name("order_worker.py")),
            str(self.manifest),
            self.url,
            str(report),
            "--timeout",
            str(timeout),
        ]
        if repeat:
            command.append("--repeat-in-process")
        process = subprocess.Popen(
            command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT
        )
        worker: Worker = {"process": process, "report": report, "log": log}
        self.workers.append(worker)
        return worker

    def result(self, worker: Worker) -> dict[str, Any]:
        process = worker["process"]
        try:
            process.wait(timeout=30)
        except subprocess.TimeoutExpired as exc:
            raise AssertionError(f"worker watchdog expired; log: {worker['log']}") from exc
        assert process.returncode == 0, worker["log"].read_text()
        assert worker["report"].exists(), "worker exited without a diagnostic result"
        return json.loads(worker["report"].read_text())

    def kill(self, worker: Worker):
        assert os.name == "posix", "SIGKILL crash contract requires a POSIX test host"
        process = worker["process"]
        assert process.poll() is None, worker["log"].read_text()
        process.send_signal(signal.SIGKILL)
        process.wait(timeout=5)
        assert process.returncode == -signal.SIGKILL
        return {"pid": process.pid, "signal": "SIGKILL", "returncode": process.returncode}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        for worker in self.workers:
            process = worker["process"]
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        for stream in self.streams:
            stream.close()
