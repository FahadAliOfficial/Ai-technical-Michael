from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from ai_shopping_agent import cli
from ai_shopping_agent.audit import AuditLogger
from ai_shopping_agent.config import Settings
from ai_shopping_agent.evaluation import runner


def test_audit_logger_persists_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path)
    logger.log("verified", "run-1", product_id="LAPTOP_001")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["event"] == "verified"
    assert payload["run_id"] == "run-1"


def test_settings_load_operational_environment(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("OPENAI_MAX_RETRIES", "4")
    monkeypatch.setenv("SHOPPING_AGENT_LOG_PATH", str(tmp_path / "agent.jsonl"))
    settings = Settings.from_env(env_file=None)
    assert settings.api_key is None
    assert settings.model == "test-model"
    assert settings.timeout_seconds == 12.5
    assert settings.max_retries == 4


def test_cli_json_and_text_modes(monkeypatch, capsys, tmp_path: Path) -> None:
    settings = Settings(log_path=tmp_path / "cli.jsonl")
    monkeypatch.setattr(cli.Settings, "from_env", classmethod(lambda cls: settings))

    monkeypatch.setattr(sys, "argv", ["shopping-agent", "--json"])
    cli.main()
    json_payload = json.loads(capsys.readouterr().out)
    assert json_payload["recommendation"]["status"] == "success"

    monkeypatch.setattr(sys, "argv", ["shopping-agent"])
    cli.main()
    text_output = capsys.readouterr().out
    assert "Mode: offline-schema-aware" in text_output
    assert "Mandatory checks:" in text_output
    assert "Verified comparison:" in text_output

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "shopping-agent",
            "I need a development laptop under ,000 with 32GB RAM and 1TB SSD",
        ],
    )
    cli.main()
    clarification_output = capsys.readouterr().out
    assert "Clarification:" in clarification_output
    assert "PowerShell" in clarification_output


def test_evaluator_parses_counts_coverage_and_failures() -> None:
    completed = subprocess.CompletedProcess(
        args=["pytest"],
        returncode=1,
        stdout="72 passed, 1 failed, 2 deselected\nTOTAL 100 10 90%",
        stderr="failure details",
    )
    result = runner._parse_test_result(completed)
    assert result["passed"] == 72
    assert result["failed"] == 1
    assert result["coverage_percent"] == 90
    assert "failure details" in result["output"]


def test_evaluator_run_records_gate_evidence(monkeypatch, tmp_path: Path) -> None:
    clean = {
        "passed": 10,
        "failed": 0,
        "errors": 0,
        "skipped": 0,
        "deselected": 0,
        "total": 10,
        "success_rate_percent": 100.0,
        "exit_code": 0,
        "coverage_percent": 90,
        "output": None,
        "command": "pytest",
        "duration_seconds": 0.1,
    }
    monkeypatch.setattr(runner, "_run_pytest", lambda *args, **kwargs: dict(clean))
    output = tmp_path / "evaluation.json"
    report = runner.run(output)
    assert report["quality"]["score"] == 5
    assert report["quality"]["coverage_percent"] == 90
    assert output.is_file()
