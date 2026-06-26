"""Tests for renderers."""

from __future__ import annotations

from pathlib import Path

from local_llm_setup.frameworks import get_plugin
from local_llm_setup.models.config import ApiKeyEntry, NginxConfig, SetupConfig
from local_llm_setup.profiles import load_profile
from local_llm_setup.renderers import generate
from local_llm_setup.renderers.compose import render_compose, render_env
from local_llm_setup.renderers.nginx import render_api_keys_map, render_nginx_conf


def test_render_ollama_compose():
    setup = load_profile(Path("llm_local/profiles/sample.yaml"))
    text = render_compose(setup)
    assert "ollama" in text
    assert "11434" in text
    assert "ollama_data_sample" in text
    assert "OLLAMA_HOST" in text
    assert "0.0.0.0:11434" in text


def test_render_compose_uses_custom_docker_image():
    setup = load_profile(Path("llm_local/profiles/sample.yaml"))
    setup.frameworks[0].image_tag = "ollama/ollama:0.5.4"
    text = render_compose(setup)
    assert "image: ollama/ollama:0.5.4" in text
    assert "ollama/ollama:latest" not in text
    setup = load_profile(Path("llm_local/profiles/sample.yaml"))
    setup.hf_token = "hf_test_token"
    env = render_env(setup)
    assert "HF_TOKEN=hf_test_token" in env


def test_render_nginx_and_api_keys():
    setup = load_profile(Path("llm_local/profiles/sample.yaml"))
    setup.nginx = NginxConfig(
        enabled=True,
        api_key_auth=True,
        api_keys=[ApiKeyEntry(key="test-key-123", label="dev")],
    )
    conf = render_nginx_conf(setup)
    assert "proxy_pass" in conf
    assert "api_keys.map" in conf
    assert "auth_bearer_token" in conf
    amap = render_api_keys_map(setup)
    assert "test-key-123" in amap


def test_generate_dry_run(tmp_path: Path):
    setup = load_profile(Path("llm_local/profiles/sample.yaml"))
    setup.output_dir = tmp_path
    result = generate(setup, dry_run=True)
    assert "ollama" in result.compose_yaml
    assert not (tmp_path / "docker-compose.yaml").exists()


def test_generate_writes_files(tmp_path: Path, monkeypatch):
    setup = load_profile(Path("llm_local/profiles/sample.yaml"))
    out = tmp_path / "llm_local" / "output" / "sample"
    setup.output_dir = out
    monkeypatch.chdir(tmp_path)
    generate(setup)
    assert (out / "docker-compose.yaml").exists()
    assert (out / ".env").exists()
    assert (out / "RUN.md").exists()


def test_vllm_compose_has_model():
    from local_llm_setup.models.config import Framework

    plugin = get_plugin(Framework.VLLM)
    fc = plugin.default_config("meta-llama/Meta-Llama-3-8B-Instruct")
    setup = SetupConfig(frameworks=[fc])
    text = render_compose(setup)
    assert "vllm" in text
    assert "meta-llama/Meta-Llama-3-8B-Instruct" in text
