"""Tests for multi-instance support."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml

from local_llm_setup.instances import collect_reserved_ports, list_instances
from local_llm_setup.instances.registry import stack_status
from local_llm_setup.models.config import (
    Framework,
    FrameworkConfig,
    ModelConfig,
    NginxConfig,
    SetupConfig,
)
from local_llm_setup.paths import compose_project_name, normalize_output_dir, output_dir_for
from local_llm_setup.ports import resolve_port_conflicts
from local_llm_setup.renderers.compose import render_compose, tunnel_container_name


def test_output_dir_for_profile_name():
    assert output_dir_for("my-ollama") == Path("llm_local/output/my-ollama")


def test_compose_uses_per_profile_container_names():
    config = SetupConfig(
        profile_name="prod",
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="llama3.2"),
                port=11434,
            )
        ],
        nginx=NginxConfig(enabled=True, listen_port=8080, tunnel_enabled=True),
    )
    compose = render_compose(config)
    assert "0.0.0.0:11434:11434" in compose
    assert "container_name: local-llm-prod-ollama" in compose
    assert "container_name: local-llm-prod-nginx" in compose
    assert "container_name: local-llm-prod-tunnel" in compose
    assert "local-llm-setup-prod-local_llm" in compose
    assert "./model-ollama:/root/.ollama" in compose
    assert compose_project_name("prod") == "local-llm-prod"
    assert tunnel_container_name(config) == "local-llm-prod-tunnel"


def test_collect_reserved_ports_from_other_stacks(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out_a = tmp_path / "llm_local" / "output" / "stack-a"
    out_b = tmp_path / "llm_local" / "output" / "stack-b"
    out_a.mkdir(parents=True)
    out_b.mkdir(parents=True)
    (out_a / "docker-compose.yaml").write_text(
        yaml.dump(
            {
                "services": {
                    "nginx": {"ports": ["0.0.0.0:8080:80"]},
                    "ollama": {"ports": ["127.0.0.1:11434:11434"]},
                }
            }
        ),
        encoding="utf-8",
    )

    reserved = collect_reserved_ports(exclude_output_dir=out_b)
    assert 8080 in reserved
    assert 11434 in reserved

    reserved_self = collect_reserved_ports(exclude_output_dir=out_a)
    assert 8080 not in reserved_self


def test_resolve_port_conflicts_avoids_other_stack_ports(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out_other = tmp_path / "llm_local" / "output" / "other"
    out_other.mkdir(parents=True)
    (out_other / "docker-compose.yaml").write_text(
        yaml.dump({"services": {"nginx": {"ports": ["0.0.0.0:8080:80"]}}}),
        encoding="utf-8",
    )

    config = SetupConfig(
        profile_name="new-stack",
        output_dir=normalize_output_dir("new-stack"),
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

    with patch("local_llm_setup.ports.is_port_free", return_value=True):
        resolved, warnings = resolve_port_conflicts(
            config,
            external_reserved=collect_reserved_ports(exclude_output_dir=config.output_dir),
        )

    assert resolved.nginx.listen_port == 8081
    assert any("nginx" in w.lower() for w in warnings)


def test_resolve_port_conflicts_same_provider_avoids_listen_port(tmp_path: Path, monkeypatch):
    """Second Ollama instance should not reuse provider port 11434."""
    monkeypatch.chdir(tmp_path)
    profiles = tmp_path / "llm_local" / "profiles"
    profiles.mkdir(parents=True)
    (profiles / "ollama-a.yaml").write_text(
        yaml.dump(
            {
                "profile_name": "ollama-a",
                "frameworks": [
                    {"framework": "ollama", "model": {"name": "llama3.2"}, "port": 11434}
                ],
                "nginx": {"enabled": True, "listen_port": 8080},
            }
        ),
        encoding="utf-8",
    )

    config = SetupConfig(
        profile_name="ollama-b",
        output_dir=normalize_output_dir("ollama-b"),
        frameworks=[
            FrameworkConfig(
                framework=Framework.OLLAMA,
                model=ModelConfig(name="llama3.2"),
                port=11434,
                extra_env={"OLLAMA_HOST": "0.0.0.0:11434"},
            )
        ],
        nginx=NginxConfig(enabled=True, listen_port=8080, bind_host="0.0.0.0"),
    )

    with patch("local_llm_setup.ports.is_port_free", return_value=True):
        resolved, warnings = resolve_port_conflicts(
            config,
            external_reserved=collect_reserved_ports(
                exclude_output_dir=config.output_dir,
                exclude_profile="ollama-b",
            ),
        )

    assert resolved.frameworks[0].port == 11435
    assert resolved.frameworks[0].extra_env["OLLAMA_HOST"] == "0.0.0.0:11435"
    assert resolved.nginx.listen_port == 8081
    assert any("ollama" in w.lower() for w in warnings)


def test_stack_status_detects_running_container(tmp_path: Path, monkeypatch):
    compose_dir = tmp_path / "smollm-1"
    compose_dir.mkdir()
    (compose_dir / "docker-compose.yaml").write_text(
        "services:\n  ollama:\n    container_name: local-llm-smollm-1-ollama\n",
        encoding="utf-8",
    )

    def fake_running(name: str) -> bool:
        return name == "local-llm-smollm-1-ollama"

    monkeypatch.setattr("local_llm_setup.instances.registry.is_container_running", fake_running)
    assert stack_status(compose_dir) == "running"


def test_list_instances_reads_profiles(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    profiles = tmp_path / "llm_local" / "profiles"
    profiles.mkdir(parents=True)
    profile = profiles / "demo.yaml"
    profile.write_text(
        yaml.dump(
            {
                "profile_name": "demo",
                "output_dir": "llm_local/output/demo",
                "frameworks": [
                    {
                        "framework": "ollama",
                        "model": {"name": "llama3.2"},
                        "port": 11434,
                    }
                ],
                "nginx": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    with patch("local_llm_setup.instances.registry.stack_status", return_value="not_deployed"):
        rows = list_instances()

    assert len(rows) == 1
    assert rows[0].profile_name == "demo"
    assert rows[0].output_dir == Path("llm_local/output/demo")
