"""Resolve host port conflicts before generate/deploy."""

from __future__ import annotations

from pathlib import Path

import yaml

from local_llm_setup.detect.host import is_port_free
from local_llm_setup.models.config import Framework, FrameworkConfig, SetupConfig, framework_default_port

_BIND_HOSTS = frozenset({"127.0.0.1", "0.0.0.0"})


def _check_host(bind_host: str) -> str:
    return bind_host if bind_host in _BIND_HOSTS else "0.0.0.0"


def find_free_port(
    start: int,
    *,
    host: str = "0.0.0.0",
    reserved: set[int] | None = None,
    max_tries: int = 512,
) -> int:
    """Return the first port >= start that is free on host and not reserved."""
    taken = reserved or set()
    port = start
    for _ in range(max_tries):
        if port not in taken and is_port_free(port, host):
            return port
        port += 1
    raise ValueError(f"No free port found near {start} on {host}")


def _pick_framework_port(
    *,
    framework: Framework,
    current: int,
    host: str,
    reserved: set[int],
    reason: str,
) -> tuple[int, str | None]:
    """Choose a free port, preferring the framework's canonical default."""
    if current not in reserved and is_port_free(current, host):
        return current, None

    ideal = framework_default_port(framework)
    start = ideal if ideal not in reserved and is_port_free(ideal, host) else current + 1
    new_port = find_free_port(start, host=host, reserved=reserved)
    if new_port == current:
        return current, None
    return new_port, f"Port {current} {reason}; {framework.value} uses {new_port}."


def split_host_port(value: str) -> tuple[str | None, int | None]:
    """Parse ``host:port`` values such as ``0.0.0.0:11434``."""
    if ":" not in value:
        return None, None
    host, port_str = value.rsplit(":", 1)
    try:
        return (host or "0.0.0.0"), int(port_str)
    except ValueError:
        return None, None


def sync_ollama_listen_port(fc: FrameworkConfig, old_port: int) -> None:
    """Keep OLLAMA_HOST aligned when a framework port is auto-adjusted."""
    if fc.framework != Framework.OLLAMA or fc.port == old_port:
        return

    bind = "0.0.0.0"
    existing = fc.extra_env.get("OLLAMA_HOST")
    if existing:
        host, port = split_host_port(existing)
        if host:
            bind = host
        # Respect deliberate custom listen ports in extra_env.
        if port is not None and port != old_port:
            return
    fc.extra_env["OLLAMA_HOST"] = f"{bind}:{fc.port}"


def ollama_host_for_port(fc: FrameworkConfig) -> str:
    """Return OLLAMA_HOST with the bind address from config and fc.port."""
    bind = "0.0.0.0"
    existing = fc.extra_env.get("OLLAMA_HOST")
    if existing:
        host, _ = split_host_port(existing)
        if host:
            bind = host
    return f"{bind}:{fc.port}"


def _bump_internal_port(
    *,
    framework: Framework,
    current: int,
    reserved: set[int],
    reason: str,
) -> tuple[int, str | None]:
    if current not in reserved:
        return current, None
    port = current + 1
    while port in reserved:
        port += 1
    return port, f"Port {current} {reason}; {framework.value} uses {port}."


def resolve_port_conflicts(config: SetupConfig) -> tuple[SetupConfig, list[str]]:
    """Assign unique, available host ports for every framework and nginx."""
    warnings: list[str] = []
    # Docker publishes each host port number once, regardless of bind IP.
    reserved: set[int] = set()

    for fc in config.frameworks:
        old = fc.port
        if config.nginx.enabled:
            if old in reserved:
                fc.port, message = _bump_internal_port(
                    framework=fc.framework,
                    current=old,
                    reserved=reserved,
                    reason="already used by another framework in this stack",
                )
                if message:
                    warnings.append(message)
                sync_ollama_listen_port(fc, old)
            reserved.add(fc.port)
            continue

        host = _check_host(fc.bind_host)
        if old in reserved:
            reason = "already used by another framework in this stack"
        elif not is_port_free(old, host):
            reason = f"in use on {host}"
        else:
            reserved.add(old)
            continue

        fc.port, message = _pick_framework_port(
            framework=fc.framework,
            current=old,
            host=host,
            reserved=reserved,
            reason=reason,
        )
        if fc.port != old:
            sync_ollama_listen_port(fc, old)
        if message:
            warnings.append(message)
        reserved.add(fc.port)

    if len(config.frameworks) > 1 and config.nginx.enabled:
        warnings.append(
            "nginx proxies only the first framework; other frameworks are reachable on their direct ports."
        )

    if config.nginx.enabled:
        host = _check_host(config.nginx.bind_host)
        old = config.nginx.listen_port
        if old in reserved:
            reason = "already used by another service in this stack"
        elif not is_port_free(old, host):
            reason = f"in use on {host}"
        else:
            reserved.add(old)
            if config.frameworks:
                config.nginx.upstream_port = config.frameworks[0].port
            return config, warnings

        config.nginx.listen_port = find_free_port(old, host=host, reserved=reserved)
        warnings.append(f"Port {old} {reason}; nginx will listen on {config.nginx.listen_port}.")
        reserved.add(config.nginx.listen_port)
        if config.frameworks:
            config.nginx.upstream_port = config.frameworks[0].port

    return config, warnings


def parse_published_port(mapping: str) -> int | None:
    """Extract the host port from a Docker Compose port mapping string."""
    parts = str(mapping).strip().split(":")
    if len(parts) == 3:
        try:
            return int(parts[1])
        except ValueError:
            return None
    if len(parts) == 2:
        try:
            return int(parts[0])
        except ValueError:
            return None
    return None


def apply_compose_ports(config: SetupConfig, output_dir: Path | str) -> SetupConfig:
    """Sync listen/publish ports from the generated docker-compose.yaml.

    Wizard state can drift after ``prepare_config`` (e.g. port 80 was busy at
    deploy but free later). The compose file is the source of truth for what
    is actually published on the host.
    """
    compose_path = Path(output_dir) / "docker-compose.yaml"
    if not compose_path.is_file():
        return config

    try:
        data = yaml.safe_load(compose_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return config

    services: dict = data.get("services") or {}
    by_service = {fc.framework.value.replace(".", ""): fc for fc in config.frameworks}

    if config.nginx.enabled:
        nginx = services.get("nginx") or {}
        ports = nginx.get("ports") or []
        if ports:
            host_port = parse_published_port(str(ports[0]))
            if host_port is not None:
                config.nginx.listen_port = host_port
        if config.frameworks:
            config.nginx.upstream_port = config.frameworks[0].port
        return config

    for name, service in services.items():
        if name in {"nginx", "cloudflared"}:
            continue
        fc = by_service.get(name)
        if fc is None:
            continue
        ports = service.get("ports") or []
        if not ports:
            continue
        host_port = parse_published_port(str(ports[0]))
        if host_port is not None:
            fc.port = host_port
            if fc.publish_port is None:
                fc.publish_port = host_port

    return config
