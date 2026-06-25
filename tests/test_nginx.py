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


def test_compose_includes_tunnel_when_enabled():
    compose = render_compose(_setup())
    assert "cloudflared:" in compose
    assert "trycloudflare" not in compose
    assert "http://nginx:80" in compose
