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
from local_llm_setup.ports import (
    apply_compose_ports,
    find_free_port,
    parse_published_port,
    resolve_port_conflicts,
)
from local_llm_setup.renderers import prepare_config
from local_llm_setup.renderers.compose import render_compose
from local_llm_setup.renderers.nginx import render_nginx_conf


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
    config.frameworks[0].extra_env = {"OLLAMA_HOST": "0.0.0.0:11434"}

    def fake_free(port: int, host: str = "127.0.0.1") -> bool:
        return port != 11434

    with patch("local_llm_setup.ports.is_port_free", side_effect=fake_free):
        resolved, warnings = resolve_port_conflicts(config)

    assert resolved.frameworks[0].port == 11435
    assert resolved.frameworks[0].extra_env["OLLAMA_HOST"] == "0.0.0.0:11435"
    assert any("11434" in w and "11435" in w for w in warnings)


def test_resolve_port_keeps_ollama_port_when_nginx_hides_host_mapping():
    config = _ollama_config(port=11434, nginx_port=8080)
    config.frameworks[0].extra_env = {"OLLAMA_HOST": "0.0.0.0:11434"}

    def fake_free(port: int, host: str = "0.0.0.0") -> bool:
        if host == "127.0.0.1" and port == 11434:
            return False
        return port != 8080

    with patch("local_llm_setup.ports.is_port_free", side_effect=fake_free):
        resolved, warnings = resolve_port_conflicts(config)

    assert resolved.frameworks[0].port == 11434
    assert resolved.frameworks[0].extra_env["OLLAMA_HOST"] == "0.0.0.0:11434"
    assert resolved.nginx.upstream_port == 11434
    assert resolved.nginx.listen_port == 8081
    assert any("nginx" in w.lower() for w in warnings)


def test_prepare_config_syncs_ollama_host_into_compose_and_nginx():
    config = _ollama_config(port=11434, nginx=False)
    config.frameworks[0].bind_host = "127.0.0.1"
    config.frameworks[0].extra_env = {"OLLAMA_HOST": "0.0.0.0:11434"}

    def fake_free(port: int, host: str = "127.0.0.1") -> bool:
        return port != 11434

    with patch("local_llm_setup.ports.is_port_free", side_effect=fake_free), patch(
        "local_llm_setup.renderers.collect_reserved_ports", return_value=set()
    ):
        prepared, _ = prepare_config(config)

    compose = render_compose(prepared)
    nginx = render_nginx_conf(prepared)
    assert 'OLLAMA_HOST: 0.0.0.0:11435' in compose or "0.0.0.0:11435" in compose
    assert "server ollama:11435;" in nginx


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
    assert "another instance" in warnings[0]


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


def test_parse_published_port():
    assert parse_published_port("0.0.0.0:8080:80") == 8080
    assert parse_published_port("8080:80") == 8080
    assert parse_published_port("bad") is None


def test_apply_compose_ports_reads_nginx(tmp_path):
    (tmp_path / "docker-compose.yaml").write_text(
        "services:\n  nginx:\n    ports:\n    - 0.0.0.0:8080:80\n",
        encoding="utf-8",
    )
    config = _ollama_config(nginx_port=80)
    synced = apply_compose_ports(config, tmp_path)
    assert synced.nginx.listen_port == 8080
