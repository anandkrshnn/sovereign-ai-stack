import json
import subprocess
import sys
from pathlib import Path

from click.testing import CliRunner

from sovereign_ai.workflows.tamilnadu_cli import main


def test_development_cli_and_independent_verifier_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SOVEREIGN_ENV", "development")
    cli = CliRunner()
    for args in (
        ["export-trust", "--output", "trust.json"],
        ["submit", "--output", "pending.json"],
        [
            "approve",
            "--input",
            "pending.json",
            "--output",
            "approved.json",
            "--principal",
            "fixture-operator",
        ],
    ):
        result = cli.invoke(main, args)
        assert result.exit_code == 0, (result.output, result.exception)
    verifier = Path(__file__).resolve().parents[2] / "verify.py"

    def verify(tenant="default", trust="trust.json"):
        return subprocess.run(
            [
                sys.executable,
                str(verifier),
                "approved.json",
                "--trusted-keys",
                trust,
                "--tenant",
                tenant,
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    valid = verify()
    assert valid.returncode == 0
    assert json.loads(valid.stdout)["decision"] == "allowed"
    assert verify(tenant="other").returncode == 1
    Path("empty-trust.json").write_text("{}", encoding="utf-8")
    assert verify(trust="empty-trust.json").returncode == 1

    payload = json.loads(Path("approved.json").read_text(encoding="utf-8"))
    payload["request"]["value"] = "altered"
    Path("approved.json").write_text(json.dumps(payload), encoding="utf-8")
    assert verify().returncode == 1

    pending = json.loads(Path("pending.json").read_text(encoding="utf-8"))
    pending["signature"] = "invalid"
    Path("pending.json").write_text(json.dumps(pending), encoding="utf-8")
    invalid = cli.invoke(
        main,
        ["approve", "--input", "pending.json", "--output", "bad.json", "--principal", "operator"],
    )
    assert invalid.exit_code != 0 and not Path("bad.json").exists()


def test_simulator_cli_refuses_production_even_with_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SOVEREIGN_ENV", "production")
    monkeypatch.setenv("SOVEREIGN_ALLOW_SIMULATOR", "1")
    result = CliRunner().invoke(main, ["submit", "--output", "pending.json"])
    assert result.exit_code != 0
    assert "development-only" in result.output
    assert not Path("pending.json").exists()
