"""Tests for Docker deploy runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from local_llm_setup.models.config import Framework, FrameworkConfig, ModelConfig, SetupConfig
from local_llm_setup.profiles import load_profile
from local_llm_setup.runner import _wait_for_ollama, deploy, stop_stack


def _ok(*_a, **_k):
    class R:
        returncode = 0
        stdout = "ok\n"
        stderr = ""

    return R()


def test_deploy_success(tmp_path: Path):
    setup = load_profile(Path("llm_local/profiles/sample.yaml"))
    setup.output_dir = tmp_path
    (tmp_path / "docker-compose.yaml").write_text("services: {}\n")

    with patch("local_llm_setup.runner._run", side_effect=lambda cmd, cwd, **kw: __import__(
        "local_llm_setup.runner", fromlist=["DeployStep"]
    ).DeployStep(" ".join(cmd), 0, "ok", "")), patch(
        "local_llm_setup.runner._wait_for_ollama", return_value=True
    ):
        result = deploy(setup, pull=True)
    assert result.success
    assert len(result.steps) >= 2


def test_deploy_missing_compose(tmp_path: Path):
    setup = SetupConfig(frameworks=[FrameworkConfig(framework=Framework.OLLAMA, model=ModelConfig(name="x"))])
    setup.output_dir = tmp_path
    result = deploy(setup)
    assert not result.success
    assert "Missing" in (result.error or "")


def test_wait_for_ollama_ready(tmp_path: Path):
    calls = 0

    def fake_run(cmd, **kw):
        nonlocal calls
        calls += 1
        class R:
            returncode = 0 if calls >= 2 else 1
            stdout = ""
            stderr = ""

        return R()

    with patch("local_llm_setup.runner.subprocess.run", side_effect=fake_run), patch(
        "local_llm_setup.runner.time.sleep"
    ):
        assert _wait_for_ollama(["docker", "compose"], tmp_path, timeout=30) is True
    assert calls == 2


def test_deploy_ollama_pull_step(tmp_path: Path):
    setup = load_profile(Path("llm_local/profiles/sample.yaml"))
    setup.output_dir = tmp_path
    (tmp_path / "docker-compose.yaml").write_text("services: {}\n")
    calls: list[str] = []

    def fake_run(cmd, cwd, **kw):
        calls.append(" ".join(cmd))
        from local_llm_setup.runner import DeployStep

        return DeployStep(" ".join(cmd), 0, "", "")

    with patch("local_llm_setup.runner._run", side_effect=fake_run), patch(
        "local_llm_setup.runner._wait_for_ollama", return_value=True
    ):
        result = deploy(setup, pull=False)
    assert result.success
    assert any("ollama pull" in c for c in calls)


def test_stop_stack_success(tmp_path: Path):
    (tmp_path / "docker-compose.yaml").write_text("services: {}\n")
    calls: list[str] = []

    def fake_run(cmd, cwd, **kw):
        calls.append(" ".join(cmd))
        from local_llm_setup.runner import DeployStep

        return DeployStep(" ".join(cmd), 0, "", "")

    with patch("local_llm_setup.runner._run", side_effect=fake_run):
        result = stop_stack(tmp_path)

    assert result.success
    assert any("compose ps" in c or "ps" in c for c in calls)
    assert any("down" in c for c in calls)


def test_stop_stack_missing_compose(tmp_path: Path):
    result = stop_stack(tmp_path)
    assert not result.success
    assert "Missing" in (result.error or "")
