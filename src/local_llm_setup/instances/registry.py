"""Discover saved profiles, running stacks, and reserved host ports."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from local_llm_setup.models.config import SetupConfig
from local_llm_setup.paths import (
    OUTPUT_DIR,
    PROFILES_DIR,
    compose_project_name,
    normalize_output_dir,
    project_name_for_output_dir,
)
from local_llm_setup.ports import parse_published_port
from local_llm_setup.profiles import load_profile


@dataclass
class InstanceInfo:
    profile_name: str
    profile_path: Path
    output_dir: Path
    status: str  # running | stopped | not_deployed
    ports: dict[str, int] = field(default_factory=dict)
    frameworks: list[str] = field(default_factory=list)
    nginx_enabled: bool = False
    tunnel_enabled: bool = False

    @property
    def ports_summary(self) -> str:
        if not self.ports:
            return "—"
        return ", ".join(f"{name}:{port}" for name, port in sorted(self.ports.items()))


def _ports_from_compose(path: Path) -> dict[str, int]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return {}

    ports: dict[str, int] = {}
    for name, service in (data.get("services") or {}).items():
        for mapping in service.get("ports") or []:
            host_port = parse_published_port(str(mapping))
            if host_port is not None:
                ports[name] = host_port
    return ports


def _compose_dirs(*, exclude: Path | None = None) -> list[Path]:
    dirs: list[Path] = []
    exclude_resolved = exclude.resolve() if exclude else None

    root_compose = OUTPUT_DIR / "docker-compose.yaml"
    if root_compose.is_file():
        if exclude_resolved is None or OUTPUT_DIR.resolve() != exclude_resolved:
            dirs.append(OUTPUT_DIR)

    if OUTPUT_DIR.is_dir():
        for sub in sorted(OUTPUT_DIR.iterdir()):
            if not sub.is_dir():
                continue
            if (sub / "docker-compose.yaml").is_file():
                if exclude_resolved is not None and sub.resolve() == exclude_resolved:
                    continue
                dirs.append(sub)
    return dirs


def _ports_from_config(config: SetupConfig) -> set[int]:
    """Ports claimed by a profile — host-published and provider listen ports."""
    ports: set[int] = set()
    if config.nginx.enabled:
        ports.add(config.nginx.listen_port)
    for fc in config.frameworks:
        ports.add(fc.port)
        if fc.publish_port is not None:
            ports.add(fc.publish_port)
        if not config.nginx.enabled:
            ports.add(fc.publish_port if fc.publish_port is not None else fc.port)
    return ports


def collect_reserved_ports(
    *,
    exclude_output_dir: Path | None = None,
    exclude_profile: str | None = None,
) -> set[int]:
    """Host and provider listen ports used by other instances."""
    reserved: set[int] = set()
    exclude_resolved = exclude_output_dir.resolve() if exclude_output_dir else None

    for out_dir in _compose_dirs(exclude=exclude_output_dir):
        for port in _ports_from_compose(out_dir / "docker-compose.yaml").values():
            reserved.add(port)

    for profile_path in list_profile_paths():
        try:
            config = load_profile(profile_path)
        except (OSError, ValueError, yaml.YAMLError):
            continue
        profile_name = config.profile_name or profile_path.stem
        if exclude_profile and profile_name == exclude_profile:
            continue
        out_dir = normalize_output_dir(profile_name, config.output_dir)
        if exclude_resolved is not None and out_dir.resolve() == exclude_resolved:
            continue
        reserved.update(_ports_from_config(config))

    return reserved


def container_names_from_compose(compose_file: Path) -> list[str]:
    """Return explicit container_name values from a compose file."""
    try:
        data = yaml.safe_load(compose_file.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    names: list[str] = []
    for service in (data.get("services") or {}).values():
        name = service.get("container_name")
        if name:
            names.append(str(name))
    return names


def images_from_compose(compose_file: Path) -> list[str]:
    """Return Docker image references from a compose file."""
    try:
        data = yaml.safe_load(compose_file.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return []
    images: list[str] = []
    for service in (data.get("services") or {}).values():
        image = service.get("image")
        if image:
            images.append(str(image))
    return images


def docker_image_exists(image: str) -> bool:
    """Return True when the image is already present on the Docker host."""
    try:
        result = subprocess.run(
            ["docker", "image", "inspect", image],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


def missing_compose_images(compose_file: Path) -> list[str]:
    """Images referenced in compose that are not present locally."""
    return [image for image in images_from_compose(compose_file) if not docker_image_exists(image)]


def is_container_running(name: str) -> bool:
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def any_container_running(names: list[str]) -> bool:
    return any(is_container_running(name) for name in names)


def compose_project_candidates(output_dir: Path, config: SetupConfig | None = None) -> list[str]:
    """Docker Compose project names that may have been used to start a stack."""
    seen: set[str] = set()
    candidates: list[str] = []

    def add(name: str) -> None:
        if name and name not in seen:
            seen.add(name)
            candidates.append(name)

    if config is not None:
        add(compose_project_name(config.profile_name))
    add(project_name_for_output_dir(output_dir))
    add(output_dir.name)
    return candidates


def _compose_has_running(compose_file: Path, output_dir: Path, project: str) -> bool:
    try:
        result = subprocess.run(
            [
                "docker",
                "compose",
                "-p",
                project,
                "-f",
                str(compose_file),
                "ps",
                "--status",
                "running",
                "-q",
            ],
            cwd=output_dir,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def stack_status(output_dir: Path) -> str:
    """Return running, stopped, or not_deployed for an output directory."""
    compose_file = output_dir / "docker-compose.yaml"
    if not compose_file.is_file():
        return "not_deployed"

    containers = container_names_from_compose(compose_file)
    if containers and any_container_running(containers):
        return "running"

    for project in compose_project_candidates(output_dir):
        if _compose_has_running(compose_file, output_dir, project):
            return "running"
    return "stopped"


def list_running_instances() -> list[InstanceInfo]:
    """Instances with at least one running container."""
    return [inst for inst in list_instances() if inst.status == "running"]


def list_profile_paths() -> list[Path]:
    if not PROFILES_DIR.is_dir():
        return []
    return sorted(PROFILES_DIR.glob("*.yaml"))


def _config_ports(config: SetupConfig) -> dict[str, int]:
    ports: dict[str, int] = {}
    for fc in config.frameworks:
        name = fc.framework.value.replace(".", "")
        ports[name] = fc.port
    if config.nginx.enabled:
        ports["nginx"] = config.nginx.listen_port
    return ports


def list_instances() -> list[InstanceInfo]:
    """List saved profiles with deployment status and published ports."""
    instances: list[InstanceInfo] = []
    seen: set[str] = set()

    for profile_path in list_profile_paths():
        try:
            config = load_profile(profile_path)
        except (OSError, ValueError, yaml.YAMLError):
            continue

        profile_name = config.profile_name or profile_path.stem
        output_dir = normalize_output_dir(profile_name, config.output_dir)
        compose_ports = _ports_from_compose(output_dir / "docker-compose.yaml")
        ports = compose_ports or _config_ports(config)

        instances.append(
            InstanceInfo(
                profile_name=profile_name,
                profile_path=profile_path,
                output_dir=output_dir,
                status=stack_status(output_dir),
                ports=ports,
                frameworks=[fc.framework.value for fc in config.frameworks],
                nginx_enabled=config.nginx.enabled,
                tunnel_enabled=config.nginx.tunnel_enabled,
            )
        )
        seen.add(profile_name)

    if OUTPUT_DIR.is_dir():
        for sub in sorted(OUTPUT_DIR.iterdir()):
            if not sub.is_dir() or sub.name in seen:
                continue
            compose = sub / "docker-compose.yaml"
            if not compose.is_file():
                continue
            instances.append(
                InstanceInfo(
                    profile_name=sub.name,
                    profile_path=PROFILES_DIR / f"{sub.name}.yaml",
                    output_dir=sub,
                    status=stack_status(sub),
                    ports=_ports_from_compose(compose),
                )
            )

    legacy = OUTPUT_DIR / "docker-compose.yaml"
    if legacy.is_file() and "output" not in seen:
        instances.append(
            InstanceInfo(
                profile_name="output",
                profile_path=PROFILES_DIR / "default.yaml",
                output_dir=OUTPUT_DIR,
                status=stack_status(OUTPUT_DIR),
                ports=_ports_from_compose(legacy),
            )
        )

    return instances
