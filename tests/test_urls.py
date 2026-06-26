"""Tests for access URL builder."""

from __future__ import annotations

from unittest.mock import patch

from local_llm_setup.models.config import (
    ApiKeyEntry,
    Framework,
    FrameworkConfig,
    ModelConfig,
    NginxConfig,
    SetupConfig,
)
from local_llm_setup.renderers import normalize_access
from local_llm_setup.urls import (
    build_access_urls,
    build_curl_test_commands,
    enrich_access_urls,
    format_access_lines,
    render_access_md,
    resolve_api_key,
)


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
    with patch("local_llm_setup.urls.get_public_ip", return_value=None), patch(
        "local_llm_setup.urls.get_lan_ip", return_value="192.168.1.10"
    ):
        urls = build_access_urls(config)
    assert urls.local_url == "http://127.0.0.1:8080/"
    assert urls.lan_urls == ["http://192.168.1.10:8080/"]
    assert urls.openai_base_url == "http://192.168.1.10:8080/v1"
    assert urls.external is True
    assert urls.health_url == "http://127.0.0.1:8080/health"
    assert "Ollama" in urls.api_hint
    assert urls.uses_public_ip is False


def test_nginx_urls_use_public_ip_when_available():
    config = SetupConfig(
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="llama3.2"),
                port=11434,
                bind_host="127.0.0.1",
            )
        ],
        nginx=NginxConfig(enabled=True, listen_port=8081, bind_host="0.0.0.0"),
    )
    with patch("local_llm_setup.urls.get_public_ip", return_value="8.8.8.8"), patch(
        "local_llm_setup.urls.get_lan_ip", return_value="192.168.1.191"
    ):
        urls = build_access_urls(config)

    assert urls.lan_urls == ["http://8.8.8.8:8081/"]
    assert urls.openai_base_url == "http://8.8.8.8:8081/v1"
    assert urls.ollama_base_url == "http://8.8.8.8:8081"
    assert urls.private_lan_url == "http://192.168.1.191:8081/"
    assert urls.uses_public_ip is True
    lines = format_access_lines(urls, markup=False)
    assert any("public IP:" in line for line in lines)
    assert any("LAN:" in line for line in lines)


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
    with patch("local_llm_setup.urls.get_public_ip", return_value=None), patch(
        "local_llm_setup.urls.get_lan_ip", return_value="192.168.1.10"
    ):
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
    with patch("local_llm_setup.urls.get_public_ip", return_value=None), patch(
        "local_llm_setup.urls.get_lan_ip", return_value="192.168.1.10"
    ):
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
    with patch("local_llm_setup.urls.get_public_ip", return_value=None), patch(
        "local_llm_setup.urls.get_lan_ip", return_value="192.168.1.10"
    ):
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
    with patch("local_llm_setup.urls.get_public_ip", return_value="8.8.8.8"), patch(
        "local_llm_setup.urls.get_lan_ip", return_value="192.168.1.191"
    ):
        base = build_access_urls(config)
    enriched = enrich_access_urls(
        config,
        base,
        tunnel_url="https://example.trycloudflare.com",
    )
    assert enriched.tunnel_url == "https://example.trycloudflare.com"
    assert enriched.tunnel_openai_base_url == "https://example.trycloudflare.com/v1"
    assert any("trycloudflare.com" in c for c in enriched.tunnel_test_commands)
    assert any("8.8.8.8" in c for c in enriched.test_commands)


def test_is_public_ipv4_helper():
    from local_llm_setup.urls import _is_public_ipv4

    assert _is_public_ipv4("8.8.8.8") is True
    assert _is_public_ipv4("192.168.1.1") is False
    assert _is_public_ipv4("10.0.0.1") is False
    assert _is_public_ipv4("not-an-ip") is False


def test_curl_test_commands_include_api_key(tmp_path):
    (tmp_path / "api_keys.map").write_text(
        '"secret-key-abc" 1;  # default\n',
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
    cmds = build_curl_test_commands(config, host="127.0.0.1", port=8080, output_dir=tmp_path)
    assert cmds[0] == "curl -sSf http://127.0.0.1:8080/health"
    assert "X-API-Key: secret-key-abc" in cmds[1]
    assert "/api/tags" in cmds[1]
    assert "Authorization: Bearer secret-key-abc" in cmds[2]
    assert "/v1/models" in cmds[2]


def test_resolve_api_key_prefers_deployed_map(tmp_path):
    (tmp_path / "api_keys.map").write_text(
        '"deployed-key" 1;  # default\n',
        encoding="utf-8",
    )
    config = SetupConfig(
        output_dir=tmp_path,
        frameworks=[FrameworkConfig(framework=Framework.OLLAMA, model=ModelConfig(name="x"))],
        nginx=NginxConfig(
            enabled=True,
            api_key_auth=True,
            api_keys=[ApiKeyEntry(key="stale-wizard-key", label="default")],
        ),
    )
    assert resolve_api_key(config, tmp_path) == "deployed-key"
