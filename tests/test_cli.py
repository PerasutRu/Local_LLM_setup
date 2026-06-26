"""CLI smoke tests."""

from __future__ import annotations

from typer.testing import CliRunner

from local_llm_setup.cli import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "local-llm-setup" in result.stdout.lower() or "TUI" in result.stdout


def test_doctor_json():
    result = runner.invoke(app, ["doctor", "--json"])
    assert result.exit_code == 0
    assert "os_type" in result.stdout


def test_generate_dry_run():
    result = runner.invoke(
        app,
        ["generate", "--config", "llm_local/profiles/sample.yaml", "--dry-run"],
    )
    assert result.exit_code == 0
    assert "Validation passed" in result.stdout or "dry run" in result.stdout.lower()
