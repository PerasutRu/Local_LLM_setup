"""Tests for curl test runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from local_llm_setup.models.config import ApiKeyEntry, Framework, FrameworkConfig, ModelConfig, NginxConfig, SetupConfig
from local_llm_setup.paths import OUTPUT_DIR
from local_llm_setup.runner import run_curl_tests


def test_run_curl_tests_success():
    config = SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="tinyllama:1.1b"),
                port=11434,
            )
        ],
        nginx=NginxConfig(enabled=True, listen_port=80),
        output_dir=OUTPUT_DIR,
    )

    class FakeResult:
        returncode = 0
        stdout = '{"ok": true}'
        stderr = ""

    with patch("local_llm_setup.runner.subprocess.run", return_value=FakeResult()):
        result = run_curl_tests(config)
    assert result.success
    assert len(result.steps) >= 3


def test_run_curl_tests_uses_compose_port(tmp_path: Path):
    (tmp_path / "docker-compose.yaml").write_text(
        "services:\n  nginx:\n    ports:\n    - 0.0.0.0:9090:80\n",
        encoding="utf-8",
    )
    config = SetupConfig(
        output_dir=tmp_path,
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="tinyllama:1.1b"),
                port=11434,
            )
        ],
        nginx=NginxConfig(enabled=True, listen_port=80),
    )

    class FakeResult:
        returncode = 0
        stdout = "ok"
        stderr = ""

    with patch("local_llm_setup.runner.subprocess.run", return_value=FakeResult()) as run:
        result = run_curl_tests(config)

    assert result.success
    first_cmd = run.call_args[0][0]
    assert "127.0.0.1:9090" in " ".join(first_cmd)
    assert ":80/" not in " ".join(first_cmd)


def test_run_curl_tests_sends_api_key_header(tmp_path: Path):
    (tmp_path / "docker-compose.yaml").write_text(
        "services:\n  nginx:\n    ports:\n    - 0.0.0.0:8080:80\n",
        encoding="utf-8",
    )
    (tmp_path / "api_keys.map").write_text(
        '"my-test-key" 1;  # default\n',
        encoding="utf-8",
    )
    config = SetupConfig(
        output_dir=tmp_path,
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="tinyllama:1.1b"),
                port=11434,
            )
        ],
        nginx=NginxConfig(enabled=True, listen_port=8080, api_key_auth=True),
    )

    class FakeResult:
        returncode = 0
        stdout = "ok"
        stderr = ""

    with patch("local_llm_setup.runner.subprocess.run", return_value=FakeResult()) as run:
        result = run_curl_tests(config)

    assert result.success
    second_cmd = run.call_args_list[1][0][0]
    assert "X-API-Key: my-test-key" in " ".join(second_cmd)
