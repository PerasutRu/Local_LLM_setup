"""Profile save/load/delete."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from local_llm_setup.models.config import SetupConfig
from local_llm_setup.paths import PROFILES_DIR, normalize_output_dir, output_dir_for


def save_profile(config: SetupConfig, path: Path | None = None) -> Path:
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    config.output_dir = normalize_output_dir(config.profile_name, config.output_dir)
    dest = path or PROFILES_DIR / f"{config.profile_name}.yaml"
    data = config.model_dump(mode="json")
    dest.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return dest


def load_profile(path: Path) -> SetupConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SetupConfig.model_validate(data)


def delete_profile(profile_name: str, *, remove_output: bool = True) -> list[Path]:
    """Remove a saved profile YAML and optionally its generated output directory."""
    deleted: list[Path] = []
    profile_path = PROFILES_DIR / f"{profile_name}.yaml"
    if profile_path.is_file():
        profile_path.unlink()
        deleted.append(profile_path)

    if remove_output:
        out_dir = output_dir_for(profile_name)
        if out_dir.is_dir():
            shutil.rmtree(out_dir)
            deleted.append(out_dir)

    return deleted
