"""Tests for access URL builder."""

from __future__ import annotations

from local_llm_setup.models.config import (
    Framework,
    FrameworkConfig,
    ModelConfig,
    NginxConfig,
    SetupConfig,
)
from local_llm_setup.renderers import normalize_access
from local_llm_setup.urls import build_access_urls, build_curl_test_commands, enrich_access_urls, format_access_lines, render_access_md


def test_nginx_urls_external():
    config = SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="llama3.2"),
                port=11434,
                bind_host="127.0.0.1",
            )
        ],
        nginx=NginxConfig(enabled=True, listen_port=8080, bind_host="0.0.0.0"),
    )
    urls = build_access_urls(config)
    assert urls.local_url == "http://127.0.0.1:8080/"
    assert urls.external is True
    assert urls.health_url == "http://127.0.0.1:8080/health"
    assert "Ollama" in urls.api_hint


def test_direct_local_only():
    config = SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="llama3.2"),
                port=11434,
                bind_host="127.0.0.1",
            )
        ],
    )
    urls = build_access_urls(config)
    assert urls.local_url == "http://127.0.0.1:11434/"
    assert urls.external is False
    assert urls.lan_urls == []


def test_normalize_access_with_nginx():
    config = SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="llama3.2"),
                port=11434,
                bind_host="0.0.0.0",
            )
        ],
        nginx=NginxConfig(enabled=True, listen_port=80),
    )
    normalized = normalize_access(config)
    assert normalized.frameworks[0].bind_host == "127.0.0.1"
    assert normalized.nginx.bind_host == "0.0.0.0"


def test_format_access_lines():
    config = SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.VLLM,
                model=ModelConfig(name="org/model"),
                port=8000,
                bind_host="0.0.0.0",
            )
        ],
    )
    lines = format_access_lines(build_access_urls(config), markup=False)
    assert any("local:" in line for line in lines)


def test_curl_test_commands_include_chat():
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
    cmds = build_curl_test_commands(config, host="127.0.0.1", port=80)
    assert any("/health" in c for c in cmds)
    assert any("/api/chat" in c for c in cmds)
    assert any("/v1/chat/completions" in c for c in cmds)
    md = render_access_md(config)
    assert "## Test curl" in md
    assert "tinyllama:1.1b" in md


def test_enrich_access_urls_with_tunnel():
    config = SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="tinyllama:1.1b"),
                port=11434,
            )
        ],
        nginx=NginxConfig(enabled=True, listen_port=8080, tunnel_enabled=True),
    )
    base = build_access_urls(config)
    enriched = enrich_access_urls(
        config,
        base,
        tunnel_url="https://example.trycloudflare.com",
    )
    assert enriched.tunnel_url == "https://example.trycloudflare.com"
    assert enriched.tunnel_openai_base_url == "https://example.trycloudflare.com/v1"
    assert any("trycloudflare.com" in c for c in enriched.tunnel_test_commands)
