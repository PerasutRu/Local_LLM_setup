"""Tests for curl test runner."""

from __future__ import annotations

from unittest.mock import patch

from local_llm_setup.models.config import Framework, FrameworkConfig, ModelConfig, NginxConfig, SetupConfig
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
    )

    class FakeResult:
        returncode = 0
        stdout = '{"ok": true}'
        stderr = ""

    with patch("local_llm_setup.runner.subprocess.run", return_value=FakeResult()):
        result = run_curl_tests(config)
    assert result.success
    assert len(result.steps) >= 3
