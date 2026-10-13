"""First recovery slice: real orchestrator, real sockets, independent remote effects."""

import json

import pytest
from order_controller import OrderController
from order_remote import FakeOrderAPI


@pytest.mark.parametrize("deduplicate", [False, True], ids=["dedupe-off", "dedupe-on"])
def test_T20_normal_success(tmp_path, deduplicate):
    with (
        FakeOrderAPI(tmp_path / "remote.sqlite", deduplicate=deduplicate) as remote,
        OrderController(tmp_path, remote.url) as controller,
    ):
        result = controller.result(controller.start())
        counts = remote.counts()
        assert not remote.errors, remote.errors
        assert result["state"] == "succeeded", result
        assert counts["dispatches"] == counts["orders"] == 1, counts
        assert counts["duplicate_effects"] == counts["unauthorized"] == 0, counts
        assert len(result["receipts"]) == len(result["evidence"]) == 1, result
        receipt = result["receipts"][0]
        for field in ("tenant_id", "operation_key", "payload_digest"):
            assert receipt[field] == controller.arguments[field]
        persisted = controller.journal_observation()
        evidence = json.loads(persisted["evidence_json"])
        assert persisted["state"] == "succeeded"
        assert persisted["attempt_count"] == 1
        assert receipt["attempt_id"] == evidence["attempt_id"] == persisted["attempt_id"]
        assert evidence["owner_generation"] == persisted["owner_generation"]
        assert evidence == result["evidence"][0]
        print("T20", {"deduplicate": deduplicate, **counts, "state": result["state"]})


@pytest.mark.parametrize("deduplicate", [False, True], ids=["dedupe-off", "dedupe-on"])
def test_T07_held_response_SIGKILL_restart(tmp_path, deduplicate):
    with (
        FakeOrderAPI(
            tmp_path / "remote.sqlite", deduplicate=deduplicate, hold_response=True
        ) as remote,
        OrderController(tmp_path, remote.url) as controller,
    ):
        original = controller.start(timeout=30)
        committed = remote.committed.wait(timeout=30)
        assert committed, original["log"].read_text() or "remote commit handshake absent"
        before = remote.counts()
        assert before["dispatches"] == before["orders"] == 1, before
        assert not original["report"].exists(), "response was not actually held"
        persisted_before = controller.journal_observation()
        assert persisted_before["state"] == "in_flight"
        assert persisted_before["attempt_count"] == 1
        kill = controller.kill(original)
        # Release only after verified death; no receipt can reach the dead worker.
        remote.release_response.set()
        restarted = controller.start()
        result = controller.result(restarted)
        after = remote.counts()
        persisted_after = controller.journal_observation()
        assert persisted_after["state"] == "outcome_unknown"
        assert persisted_after["attempt_id"] == persisted_before["attempt_id"]
        assert persisted_after["attempt_count"] == 1
        assert persisted_after["owner_generation"] > persisted_before["owner_generation"]
        assert persisted_after["evidence_json"] is None
        observations = {
            "deduplicate": deduplicate,
            "kill": kill,
            "restarted_pid": result["pid"],
            "before": before,
            "after": after,
            "restarted_state": result["state"],
            "restarted_error": result["error"],
        }
        (tmp_path / "crash-observations.json").write_text(json.dumps(observations, indent=2))
        print("T07", observations)
        assert not remote.errors, remote.errors
        assert result["pid"] != kill["pid"], observations
        assert (
            after["dispatches"] == 1
            and after["orders"] == 1
            and result["state"] == "outcome_unknown"
            and not result["receipts"]
            and not result["evidence"]
        ), (
            "Restart lost execution uncertainty or blindly redispatched. "
            "Missing durable execution journal/recovery is tracked in #5. "
            f"Observed: {observations}"
        )


@pytest.mark.parametrize("deduplicate", [False, True], ids=["dedupe-off", "dedupe-on"])
def test_T21_live_timeout_after_commit(tmp_path, deduplicate):
    with (
        FakeOrderAPI(
            tmp_path / "remote.sqlite", deduplicate=deduplicate, hold_response=True
        ) as remote,
        OrderController(tmp_path, remote.url) as controller,
    ):
        worker = controller.start(timeout=0.25, repeat=True)
        committed = remote.committed.wait(timeout=30)
        assert committed, worker["log"].read_text() or "remote commit handshake absent"
        result = controller.result(worker)
        counts = remote.counts()
        assert not remote.errors, remote.errors
        assert result["state"] == result["repeat_state"] == "outcome_unknown", result
        assert result["attempts"] == 1, result
        assert counts["dispatches"] == counts["orders"] == 1, counts
        assert counts["duplicate_effects"] == counts["unauthorized"] == 0, counts
        assert result["receipts"] == result["evidence"] == [], result
        persisted = controller.journal_observation()
        assert persisted["state"] == "outcome_unknown"
        assert persisted["attempt_count"] == 1
        assert persisted["evidence_json"] is None
        print("T21", {"deduplicate": deduplicate, **counts, "state": result["state"]})
