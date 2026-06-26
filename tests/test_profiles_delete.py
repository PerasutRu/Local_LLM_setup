"""Tests for profile deletion."""

from __future__ import annotations

from pathlib import Path

from local_llm_setup.models.config import SetupConfig
from local_llm_setup.profiles import delete_profile, save_profile


def _minimal_config(profile_name: str, output_dir: Path) -> SetupConfig:
    return SetupConfig.model_validate(
        {
            "profile_name": profile_name,
            "output_dir": str(output_dir),
            "frameworks": [{"framework": "ollama", "port": 11434, "model": {"name": "tiny"}}],
        }
    )


def test_delete_profile_removes_yaml_and_output(tmp_path: Path, monkeypatch):
    profiles = tmp_path / "llm_local" / "profiles"
    output = tmp_path / "llm_local" / "output" / "demo"
    profiles.mkdir(parents=True)
    output.mkdir(parents=True)
    (output / "docker-compose.yaml").write_text("services: {}\n", encoding="utf-8")

    monkeypatch.setattr("local_llm_setup.profiles.store.PROFILES_DIR", profiles)
    monkeypatch.setattr("local_llm_setup.profiles.store.output_dir_for", lambda name: output.parent / name)

    config = _minimal_config("demo", output)
    save_profile(config)

    removed = delete_profile("demo")
    assert not (profiles / "demo.yaml").exists()
    assert not output.exists()
    assert len(removed) == 2


def test_delete_profile_missing_is_noop(tmp_path: Path, monkeypatch):
    profiles = tmp_path / "llm_local" / "profiles"
    profiles.mkdir(parents=True)
    monkeypatch.setattr("local_llm_setup.profiles.store.PROFILES_DIR", profiles)
    monkeypatch.setattr(
        "local_llm_setup.profiles.store.output_dir_for",
        lambda name: tmp_path / "llm_local" / "output" / name,
    )

    assert delete_profile("missing") == []
