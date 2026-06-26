"""Tests for skipping Docker/Ollama pulls when assets already exist."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml

from local_llm_setup.instances.registry import images_from_compose, missing_compose_images
from local_llm_setup.profiles import load_profile
from local_llm_setup.runner import deploy


def test_images_from_compose(tmp_path: Path):
    compose = tmp_path / "docker-compose.yaml"
    compose.write_text(
        yaml.dump(
            {
                "services": {
                    "ollama": {"image": "ollama/ollama:latest"},
                    "nginx": {"image": "nginx:1.27-alpine"},
                }
            }
        ),
        encoding="utf-8",
    )
    assert set(images_from_compose(compose)) == {"ollama/ollama:latest", "nginx:1.27-alpine"}


def test_missing_compose_images_filters_present(tmp_path: Path):
    compose = tmp_path / "docker-compose.yaml"
    compose.write_text(
        yaml.dump({"services": {"ollama": {"image": "ollama/ollama:latest"}}}),
        encoding="utf-8",
    )
    with patch("local_llm_setup.instances.registry.docker_image_exists", return_value=True):
        assert missing_compose_images(compose) == []
    with patch("local_llm_setup.instances.registry.docker_image_exists", return_value=False):
        assert missing_compose_images(compose) == ["ollama/ollama:latest"]


def test_deploy_skips_docker_pull_when_images_present(tmp_path: Path):
    setup = load_profile(Path("llm_local/profiles/sample.yaml"))
    setup.output_dir = tmp_path
    (tmp_path / "docker-compose.yaml").write_text(
        yaml.dump({"services": {"ollama": {"image": "ollama/ollama:latest"}}}),
        encoding="utf-8",
    )
    calls: list[str] = []

    def fake_run(cmd, cwd, **kw):
        calls.append(" ".join(cmd))
        from local_llm_setup.runner import DeployStep

        return DeployStep(" ".join(cmd), 0, "", "")

    with patch("local_llm_setup.runner.missing_compose_images", return_value=[]), patch(
        "local_llm_setup.runner._run", side_effect=fake_run
    ), patch("local_llm_setup.runner._wait_for_ollama", return_value=True), patch(
        "local_llm_setup.runner._ollama_model_installed", return_value=True
    ):
        result = deploy(setup, pull=True)

    assert result.success
    assert not any(c.startswith("docker pull ") for c in calls)
    assert any("up -d" in c for c in calls)


def test_deploy_skips_ollama_model_pull_when_present(tmp_path: Path):
    setup = load_profile(Path("llm_local/profiles/sample.yaml"))
    setup.output_dir = tmp_path
    (tmp_path / "docker-compose.yaml").write_text("services: {}\n", encoding="utf-8")
    calls: list[str] = []

    def fake_run(cmd, cwd, **kw):
        calls.append(" ".join(cmd))
        from local_llm_setup.runner import DeployStep

        return DeployStep(" ".join(cmd), 0, "", "")

    with patch("local_llm_setup.runner.missing_compose_images", return_value=[]), patch(
        "local_llm_setup.runner._run", side_effect=fake_run
    ), patch("local_llm_setup.runner._wait_for_ollama", return_value=True), patch(
        "local_llm_setup.runner._ollama_model_installed", return_value=True
    ):
        result = deploy(setup, pull=True)

    assert result.success
    assert not any("ollama pull" in c for c in calls)
