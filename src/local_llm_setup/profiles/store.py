"""Profile save/load/delete."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from local_llm_setup import paths as llm_paths
from local_llm_setup.models.config import SetupConfig


def save_profile(config: SetupConfig, path: Path | None = None) -> Path:
    llm_paths.PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    config.output_dir = llm_paths.normalize_output_dir(config.profile_name, config.output_dir)
    dest = path or llm_paths.PROFILES_DIR / f"{config.profile_name}.yaml"
    data = config.model_dump(mode="json")
    dest.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return dest


def load_profile(path: Path) -> SetupConfig:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return SetupConfig.model_validate(data)


def model_cache_paths_for_config(config: SetupConfig) -> list[Path]:
    """Resolved host paths for each framework's model cache in a profile."""
    out_dir = llm_paths.normalize_output_dir(config.profile_name, config.output_dir)
    return [
        llm_paths.resolve_model_cache_host_path(out_dir, fc.framework.value, fc.model_cache_host_path)
        for fc in config.frameworks
    ]


def delete_profile(
    profile_name: str,
    *,
    config: SetupConfig | None = None,
    remove_output: bool = True,
    remove_model_cache: bool = False,
) -> list[Path]:
    """Remove a saved profile YAML and optionally its output and model cache."""
    deleted: list[Path] = []
    profile_path = llm_paths.PROFILES_DIR / f"{profile_name}.yaml"

    if config is None and profile_path.is_file():
        try:
            config = load_profile(profile_path)
        except (OSError, ValueError, yaml.YAMLError):
            config = None

    if profile_path.is_file():
        profile_path.unlink()
        deleted.append(profile_path)

    out_dir = llm_paths.output_dir_for(profile_name)
    cache_paths: list[Path] = []
    if config:
        cache_paths = model_cache_paths_for_config(config)

    if remove_output and out_dir.is_dir():
        if remove_model_cache:
            shutil.rmtree(out_dir)
            deleted.append(out_dir)
        else:
            protected = {path.resolve() for path in cache_paths}
            for item in list(out_dir.iterdir()):
                if item.resolve() in protected:
                    continue
                if item.is_dir():
                    shutil.rmtree(item)
                else:
                    item.unlink()
                deleted.append(item)

    if remove_model_cache:
        for cache in cache_paths:
            if cache.is_dir():
                shutil.rmtree(cache)
                if cache.resolve() not in {path.resolve() for path in deleted}:
                    deleted.append(cache)

    return deleted
