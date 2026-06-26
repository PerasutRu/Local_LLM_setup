"""Profile save/load."""

from __future__ import annotations

from pathlib import Path

import yaml

from local_llm_setup.models.config import SetupConfig
from local_llm_setup.paths import PROFILES_DIR, normalize_output_dir


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
