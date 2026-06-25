"""Tests for automatic port resolution."""

from __future__ import annotations

from unittest.mock import patch

from local_llm_setup.models.config import (
    Framework,
    FrameworkConfig,
    ModelConfig,
    NginxConfig,
    SetupConfig,
)
from local_llm_setup.ports import find_free_port, resolve_port_conflicts
from local_llm_setup.renderers import prepare_config


def _ollama_config(*, port: int = 11434, nginx_port: int = 8080, nginx: bool = True) -> SetupConfig:
    fc = FrameworkConfig(
        framework=Framework.OLLAMA,
        model=ModelConfig(name="llama3.2"),
        port=port,
        bind_host="127.0.0.1",
    )
    return SetupConfig(
        frameworks=[fc],
        nginx=NginxConfig(
            enabled=nginx,
            listen_port=nginx_port,
            upstream_port=port,
            bind_host="0.0.0.0",
        ),
    )


def test_find_free_port_skips_reserved():
    with patch("local_llm_setup.ports.is_port_free", return_value=True):
        assert find_free_port(8080, reserved={8080, 8081}) == 8082


def test_resolve_port_bumps_busy_framework_port():
    config = _ollama_config(port=11434, nginx=False)
    config.nginx.enabled = False
    config.frameworks[0].bind_host = "127.0.0.1"

    def fake_free(port: int, host: str = "127.0.0.1") -> bool:
        return port != 11434

    with patch("local_llm_setup.ports.is_port_free", side_effect=fake_free):
        resolved, warnings = resolve_port_conflicts(config)

    assert resolved.frameworks[0].port == 11435
    assert any("11434" in w and "11435" in w for w in warnings)


def test_resolve_port_bumps_busy_nginx_port():
    config = _ollama_config(port=11434, nginx_port=8080)

    def fake_free(port: int, host: str = "127.0.0.0") -> bool:
        if host == "127.0.0.1" and port == 11434:
            return True
        return port != 8080

    with patch("local_llm_setup.ports.is_port_free", side_effect=fake_free):
        resolved, warnings = resolve_port_conflicts(config)

    assert resolved.nginx.listen_port == 8081
    assert resolved.nginx.upstream_port == 11434
    assert any("nginx" in w.lower() for w in warnings)


def test_prepare_config_normalizes_nginx_bind():
    config = _ollama_config()
    config.frameworks[0].bind_host = "0.0.0.0"

    with patch("local_llm_setup.ports.is_port_free", return_value=True):
        prepared, _ = prepare_config(config)

    assert prepared.frameworks[0].bind_host == "127.0.0.1"
    assert prepared.nginx.bind_host == "0.0.0.0"


def test_multi_framework_duplicate_ports_assign_canonical_defaults():
    config = SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.VLLM,
                model=ModelConfig(name="meta-llama/Meta-Llama-3-8B-Instruct"),
                port=9000,
            ),
            FrameworkConfig(
                framework=Framework.SGLANG,
                model=ModelConfig(name="meta-llama/Meta-Llama-3-8B-Instruct"),
                port=9000,
            ),
            FrameworkConfig(
                framework=Framework.LLAMACPP,
                model=ModelConfig(name="/models/model.gguf"),
                port=8080,
            ),
        ],
    )

    with patch("local_llm_setup.ports.is_port_free", return_value=True):
        resolved, warnings = resolve_port_conflicts(config)

    ports = {fc.framework: fc.port for fc in resolved.frameworks}
    assert ports[Framework.VLLM] == 9000
    assert ports[Framework.SGLANG] == 30000
    assert ports[Framework.LLAMACPP] == 8080
    assert len(warnings) == 1
    assert "another framework" in warnings[0]


def test_multi_framework_default_ports_do_not_conflict():
    config = SetupConfig(
        frameworks=[
            FrameworkConfig(framework=Framework.OLLAMA, model=ModelConfig(name="llama3.2")),
            FrameworkConfig(
                framework=Framework.VLLM,
                model=ModelConfig(name="meta-llama/Meta-Llama-3-8B-Instruct"),
            ),
            FrameworkConfig(
                framework=Framework.LLAMACPP,
                model=ModelConfig(name="/models/model.gguf"),
            ),
        ],
    )

    with patch("local_llm_setup.ports.is_port_free", return_value=True):
        resolved, warnings = resolve_port_conflicts(config)

    ports = [fc.port for fc in resolved.frameworks]
    assert ports == [11434, 8000, 8080]
    assert warnings == []


def test_multi_framework_llamacpp_and_nginx_share_default_8080():
    config = SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.LLAMACPP,
                model=ModelConfig(name="/models/model.gguf"),
                port=8080,
                bind_host="127.0.0.1",
            ),
        ],
        nginx=NginxConfig(enabled=True, listen_port=8080, upstream_port=8080, bind_host="0.0.0.0"),
    )

    with patch("local_llm_setup.ports.is_port_free", return_value=True):
        resolved, warnings = resolve_port_conflicts(config)

    assert resolved.frameworks[0].port == 8080
    assert resolved.nginx.listen_port == 8081
    assert any("nginx" in w.lower() for w in warnings)
