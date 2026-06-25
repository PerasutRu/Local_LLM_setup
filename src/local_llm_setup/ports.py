"""Resolve host port conflicts before generate/deploy."""

from __future__ import annotations

from local_llm_setup.detect.host import is_port_free
from local_llm_setup.models.config import Framework, SetupConfig, framework_default_port

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


def resolve_port_conflicts(config: SetupConfig) -> tuple[SetupConfig, list[str]]:
    """Assign unique, available host ports for every framework and nginx."""
    warnings: list[str] = []
    # Docker publishes each host port number once, regardless of bind IP.
    reserved: set[int] = set()

    for fc in config.frameworks:
        host = _check_host(fc.bind_host)
        old = fc.port
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
