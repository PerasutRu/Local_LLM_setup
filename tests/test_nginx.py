"""Tests for nginx config renderer."""

from __future__ import annotations

from local_llm_setup.models.config import (
    Framework,
    FrameworkConfig,
    ModelConfig,
    NginxConfig,
    SetupConfig,
)
from local_llm_setup.renderers.compose import render_compose
from local_llm_setup.renderers.nginx import render_nginx_conf


def _setup() -> SetupConfig:
    return SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="tinyllama:1.1b"),
                port=11434,
            )
        ],
        nginx=NginxConfig(enabled=True, listen_port=8080, tunnel_enabled=True),
    )


def test_nginx_accepts_any_host():
    conf = render_nginx_conf(_setup())
    assert "listen 80 default_server;" in conf
    assert "server_name _;" in conf
    assert "proxy_set_header Host $http_host;" in conf
    assert "proxy_buffering off;" in conf
    assert "server ollama:11434;" in conf


def test_nginx_multi_framework_paths():
    config = SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="llama3.2"),
                port=11434,
            ),
            FrameworkConfig(
                framework=Framework.VLLM,
                model=ModelConfig(name="org/model"),
                port=8000,
            ),
        ],
        nginx=NginxConfig(enabled=True, listen_port=8080),
    )
    conf = render_nginx_conf(config)
    assert "location /ollama/" in conf
    assert "location /vllm/" in conf
    assert "proxy_pass http://ollama:11434/;" in conf
    assert "proxy_pass http://vllm:8000/;" in conf


def test_compose_includes_tunnel_when_enabled():
    compose = render_compose(_setup())
    assert "cloudflared:" in compose
    assert "trycloudflare" not in compose
    assert "http://nginx:80" in compose


def test_compose_uses_shared_docker_network():
    compose = render_compose(_setup())
    assert "networks:" in compose
    assert "local_llm:" in compose
    assert "local-llm-setup-local_llm" in compose
    assert "networks:\n    - local_llm" in compose or "- local_llm" in compose
    assert "ollama:" in compose
    assert "nginx:" in compose


def test_compose_nginx_hides_framework_host_ports():
    compose = render_compose(_setup())
    assert "127.0.0.1:11434:11434" not in compose
    assert "0.0.0.0:8080:80" in compose


def test_compose_without_nginx_keeps_framework_ports():
    setup = SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="tinyllama:1.1b"),
                port=11434,
            )
        ],
        nginx=NginxConfig(enabled=False),
    )
    compose = render_compose(setup)
    assert "127.0.0.1:11434:11434" in compose
    assert "networks:" in compose


def test_nginx_api_key_auth_accepts_bearer_and_x_api_key():
    config = SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="llama3.2"),
                port=11434,
            )
        ],
        nginx=NginxConfig(enabled=True, listen_port=8080, api_key_auth=True),
    )
    conf = render_nginx_conf(config)
    assert "auth_bearer_token" in conf
    assert "api_key_to_check" in conf
    assert 'include /etc/nginx/api_keys.map' in conf
