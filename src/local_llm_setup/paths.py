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
