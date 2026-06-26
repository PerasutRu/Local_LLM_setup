"""Default on-disk paths for generated output and saved profiles."""

from __future__ import annotations

import re
from pathlib import Path

DATA_DIR = Path("llm_local")
OUTPUT_DIR = DATA_DIR / "output"
PROFILES_DIR = DATA_DIR / "profiles"


def instance_slug(profile_name: str) -> str:
    """Sanitize a profile name for Docker project/container identifiers."""
    slug = re.sub(r"[^a-z0-9_-]+", "-", profile_name.lower().strip())
    slug = slug.strip("-") or "default"
    return slug[:63]


def output_dir_for(profile_name: str) -> Path:
    """Per-profile output directory: llm_local/output/{profile_name}."""
    return OUTPUT_DIR / profile_name


def compose_project_name(profile_name: str) -> str:
    """Docker Compose project name for an isolated stack."""
    return f"local-llm-{instance_slug(profile_name)}"


def normalize_output_dir(profile_name: str, output_dir: Path | None = None) -> Path:
    """Return the canonical output directory for a profile."""
    _ = output_dir  # legacy profiles may store a custom path; we always isolate by name
    return output_dir_for(profile_name)


def project_name_for_output_dir(output_dir: Path) -> str:
    """Derive compose project name from an on-disk output directory."""
    resolved = output_dir.resolve()
    if resolved == OUTPUT_DIR.resolve():
        return compose_project_name("output")
    return compose_project_name(resolved.name)


# Container paths where each provider stores downloaded models.
_MODEL_CACHE_CONTAINER_PATHS: dict[str, str] = {
    "ollama": "/root/.ollama",
    "vllm": "/root/.cache/huggingface",
    "sglang": "/root/.cache/huggingface",
    "llamacpp": "/models",
}


def model_cache_dir_name(framework: str) -> str:
    """Output subfolder for a provider's model cache, e.g. model-ollama."""
    return f"model-{framework}"


def model_cache_dir(output_dir: Path, framework: str) -> Path:
    """Absolute path to the default per-provider model cache under an output directory."""
    return Path(output_dir) / model_cache_dir_name(framework)


def model_cache_container_path(framework: str) -> str:
    """In-container path where the provider reads/writes model files."""
    return _MODEL_CACHE_CONTAINER_PATHS[framework]


def resolve_model_cache_host_path(
    output_dir: Path,
    framework: str,
    custom: Path | None = None,
) -> Path:
    """Resolve the host path used for a provider's model cache."""
    if custom is not None:
        path = Path(custom).expanduser()
        if not path.is_absolute():
            path = Path(output_dir) / path
        return path.resolve()
    return model_cache_dir(output_dir, framework).resolve()


def model_cache_is_under_output(host_path: Path, output_dir: Path) -> bool:
    """Return True when the cache folder lives inside the profile output directory."""
    try:
        host_path.resolve().relative_to(Path(output_dir).resolve())
        return True
    except ValueError:
        return False


def model_cache_bind_mount(
    output_dir: Path,
    framework: str,
    custom: Path | None = None,
) -> str:
    """Docker-compose bind mount for a provider model cache."""
    host = resolve_model_cache_host_path(output_dir, framework, custom)
    container = model_cache_container_path(framework)
    out = Path(output_dir).resolve()
    if model_cache_is_under_output(host, out):
        rel = host.resolve().relative_to(out)
        return f"./{rel.as_posix()}:{container}"
    return f"{host}:{container}"


def model_cache_bind_mount_for_framework(
    output_dir: Path,
    framework: str,
    custom: Path | None = None,
) -> str:
    """Alias kept for readability at call sites."""
    return model_cache_bind_mount(output_dir, framework, custom)
