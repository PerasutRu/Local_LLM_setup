"""Tests for per-instance model cache paths."""

from __future__ import annotations

from pathlib import Path

import yaml

from local_llm_setup.frameworks import get_plugin
from local_llm_setup.models.config import Framework, SetupConfig
from local_llm_setup.paths import (
    model_cache_bind_mount,
    model_cache_dir,
    resolve_model_cache_host_path,
)
from local_llm_setup.profiles import delete_profile, save_profile
from local_llm_setup.renderers import generate
from local_llm_setup.renderers.compose import render_compose


def test_resolve_default_model_cache_under_output(tmp_path: Path):
    out = tmp_path / "llm_local" / "output" / "demo"
    assert resolve_model_cache_host_path(out, "ollama", None) == (out / "model-ollama").resolve()


def test_resolve_custom_absolute_model_cache(tmp_path: Path):
    out = tmp_path / "llm_local" / "output" / "demo"
    custom = tmp_path / "nas" / "ollama-models"
    assert resolve_model_cache_host_path(out, "ollama", custom) == custom.resolve()


def test_resolve_custom_relative_model_cache(tmp_path: Path):
    out = tmp_path / "llm_local" / "output" / "demo"
    resolved = resolve_model_cache_host_path(out, "vllm", Path("../shared-vllm"))
    assert resolved == (out / "../shared-vllm").resolve()


def test_compose_uses_default_relative_bind_mount():
    plugin = get_plugin(Framework.OLLAMA)
    fc = plugin.default_config("llama3.2")
    config = SetupConfig(profile_name="demo", output_dir=Path("llm_local/output/demo"), frameworks=[fc])
    text = render_compose(config)
    assert "./model-ollama:/root/.ollama" in text


def test_compose_uses_custom_absolute_bind_mount(tmp_path: Path):
    plugin = get_plugin(Framework.VLLM)
    fc = plugin.default_config("meta-llama/Meta-Llama-3-8B-Instruct")
    custom = tmp_path / "nas" / "hf-cache"
    fc.model_cache_host_path = custom
    config = SetupConfig(profile_name="demo", output_dir=tmp_path / "out", frameworks=[fc])
    text = render_compose(config)
    assert f"{custom}:/root/.cache/huggingface" in text
    assert "./model-vllm" not in text


def test_generate_creates_custom_model_cache_dir(tmp_path: Path, monkeypatch):
    plugin = get_plugin(Framework.OLLAMA)
    fc = plugin.default_config("llama3.2")
    custom = tmp_path / "data" / "my-ollama"
    fc.model_cache_host_path = custom
    out = tmp_path / "llm_local" / "output" / "demo"
    config = SetupConfig(profile_name="demo", output_dir=out, frameworks=[fc])
    monkeypatch.chdir(tmp_path)
    generate(config)
    assert custom.is_dir()
    assert (out / "docker-compose.yaml").is_file()


def test_delete_profile_keeps_model_cache_when_requested(tmp_path: Path, monkeypatch):
    profiles = tmp_path / "llm_local" / "profiles"
    out = tmp_path / "llm_local" / "output" / "demo"
    cache = out / "model-ollama"
    profiles.mkdir(parents=True)
    out.mkdir(parents=True)
    cache.mkdir()
    (cache / "blobs").write_text("data", encoding="utf-8")
    (out / "docker-compose.yaml").write_text("services: {}\n", encoding="utf-8")

    monkeypatch.setattr("local_llm_setup.paths.PROFILES_DIR", profiles)
    monkeypatch.setattr("local_llm_setup.paths.output_dir_for", lambda name: out)

    plugin = get_plugin(Framework.OLLAMA)
    fc = plugin.default_config("llama3.2")
    config = SetupConfig(profile_name="demo", output_dir=out, frameworks=[fc])
    save_profile(config)

    delete_profile("demo", config=config, remove_output=True, remove_model_cache=False)

    assert not (profiles / "demo.yaml").exists()
    assert not (out / "docker-compose.yaml").exists()
    assert cache.is_dir()
    assert (cache / "blobs").read_text(encoding="utf-8") == "data"


def test_delete_profile_removes_external_model_cache(tmp_path: Path, monkeypatch):
    profiles = tmp_path / "llm_local" / "profiles"
    out = tmp_path / "llm_local" / "output" / "demo"
    external = tmp_path / "nas" / "ollama"
    profiles.mkdir(parents=True)
    out.mkdir(parents=True)
    external.mkdir(parents=True)
    (external / "model.bin").write_text("x", encoding="utf-8")
    (out / "docker-compose.yaml").write_text("services: {}\n", encoding="utf-8")

    monkeypatch.setattr("local_llm_setup.paths.PROFILES_DIR", profiles)
    monkeypatch.setattr("local_llm_setup.paths.output_dir_for", lambda name: out)

    plugin = get_plugin(Framework.OLLAMA)
    fc = plugin.default_config("llama3.2")
    fc.model_cache_host_path = external
    config = SetupConfig(profile_name="demo", output_dir=out, frameworks=[fc])
    save_profile(config)

    delete_profile("demo", config=config, remove_output=True, remove_model_cache=True)

    assert not external.exists()
    assert not out.exists()
