"""Tests for command logging helpers."""

from __future__ import annotations

from pathlib import Path

from local_llm_setup.runner import (
    DeployStep,
    append_commands_log,
    format_shell_command,
    format_steps_summary,
)


def test_format_shell_command_with_cwd():
    cmd = format_shell_command(["docker", "compose", "up", "-d"], cwd=Path("/tmp/out"))
    assert cmd == "cd /tmp/out && docker compose up -d"


def test_format_steps_summary_marks_failures():
    steps = [
        DeployStep(command="docker compose pull", returncode=0, stdout="", stderr=""),
        DeployStep(command="docker compose up -d", returncode=1, stdout="error", stderr=""),
    ]
    lines = format_steps_summary(steps, cwd=Path("/tmp/out"))
    text = "\n".join(lines)
    assert "Commands executed" in text
    assert "docker compose pull" in text
    assert "✗ 1" in text
    assert "cd /tmp/out && docker compose up -d" in text


def test_append_commands_log(tmp_path: Path):
    steps = [DeployStep(command="docker compose ps", returncode=0, stdout="", stderr="")]
    append_commands_log(tmp_path, "deploy", steps)
    log = (tmp_path / "commands.log").read_text(encoding="utf-8")
    assert "# deploy @" in log
    assert "docker compose ps" in log
    assert "# exit 0" in log

    append_commands_log(tmp_path, "stop", steps)
    log2 = (tmp_path / "commands.log").read_text(encoding="utf-8")
    assert "# stop @" in log2
    assert log2.count("docker compose ps") == 2
