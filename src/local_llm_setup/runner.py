"""Run generated Docker Compose stacks."""

from __future__ import annotations

import re
import shlex
import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from local_llm_setup.models.config import Framework, SetupConfig
from local_llm_setup.paths import compose_project_name, project_name_for_output_dir
from local_llm_setup.ports import apply_compose_ports
from local_llm_setup.renderers.compose import tunnel_container_name
from local_llm_setup.instances import (
    any_container_running,
    compose_project_candidates,
    container_names_from_compose,
    list_running_instances,
)
from local_llm_setup.renderers import normalize_access
from local_llm_setup.urls import (
    AccessUrls,
    build_access_urls,
    build_curl_test_commands,
    enrich_access_urls,
    format_access_lines,
)

_TUNNEL_URL_RE = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def format_shell_command(cmd: list[str], *, cwd: Path | None = None) -> str:
    """Render a copy-paste shell command."""
    joined = shlex.join(cmd)
    if cwd is not None:
        return f"cd {cwd} && {joined}"
    return joined


def format_steps_summary(steps: list[DeployStep], *, cwd: Path | None = None) -> list[str]:
    """Human-readable summary of executed commands for terminal output."""
    from local_llm_setup.markup import style_heading

    if not steps:
        return []
    lines = ["", style_heading("Commands executed")]
    for index, step in enumerate(steps, start=1):
        mark = "[green]✓[/green]" if step.ok else f"[red]✗ {step.returncode}[/red]"
        lines.append(f"  {mark} [{index}] {step.command}")
    lines.append("")
    lines.append(style_heading("Copy-paste to replay"))
    for step in steps:
        argv = shlex.split(step.command)
        lines.append(f"  {format_shell_command(argv, cwd=cwd)}")
    return lines


def append_commands_log(out_dir: Path, operation: str, steps: list[DeployStep]) -> None:
    """Append executed commands to output/commands.log for later debugging."""
    if not steps:
        return
    stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    lines = [f"# {operation} @ {stamp}", ""]
    for step in steps:
        lines.append(f"# exit {step.returncode}")
        lines.append(step.command)
        lines.append("")
    log_path = out_dir / "commands.log"
    try:
        with log_path.open("a", encoding="utf-8") as handle:
            if log_path.exists() and log_path.stat().st_size > 0:
                handle.write("\n")
            handle.write("\n".join(lines))
    except OSError:
        pass


def _emit_steps_summary(
    steps: list[DeployStep],
    *,
    cwd: Path | None = None,
    on_output: Callable[[str], None] | None = None,
) -> None:
    if not on_output:
        return
    for line in format_steps_summary(steps, cwd=cwd):
        on_output(line)


def _record_run(
    out_dir: Path,
    operation: str,
    steps: list[DeployStep],
    on_output: Callable[[str], None] | None,
) -> None:
    append_commands_log(out_dir, operation, steps)
    _emit_steps_summary(steps, cwd=out_dir, on_output=on_output)
    if on_output and steps:
        on_output(f"[dim]saved to {out_dir / 'commands.log'}[/dim]")


@dataclass
class DeployStep:
    command: str
    returncode: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.returncode == 0


@dataclass
class DeployResult:
    success: bool
    steps: list[DeployStep] = field(default_factory=list)
    error: str | None = None
    access_urls: AccessUrls | None = None


def _compose_base() -> list[str]:
    try:
        r = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if r.returncode == 0:
            return ["docker", "compose"]
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return ["docker-compose"]


def _compose_cmd(
    output_dir: Path,
    *args: str,
    config: SetupConfig | None = None,
    project: str | None = None,
) -> list[str]:
    """Build docker compose argv with an isolated project name."""
    if project is None:
        project = (
            compose_project_name(config.profile_name)
            if config is not None
            else project_name_for_output_dir(output_dir)
        )
    compose_file = output_dir / "docker-compose.yaml"
    base = [*_compose_base(), "-p", project, "-f", str(compose_file), *args]
    return base


def _stop_containers_by_name(
    names: list[str],
    *,
    remove_volumes: bool,
    on_output: Callable[[str], None] | None,
) -> list[DeployStep]:
    steps: list[DeployStep] = []
    for name in names:
        if not any_container_running([name]):
            continue
        step = _run(["docker", "stop", "-t", "15", name], Path.cwd(), timeout=30, on_output=on_output)
        steps.append(step)
        rm_cmd = ["docker", "rm", "-f", name]
        steps.append(_run(rm_cmd, Path.cwd(), timeout=30, on_output=on_output))
    if remove_volumes:
        for name in names:
            _ = name  # volumes removed via compose down when project matches
    return steps


def _announce(
    on_output: Callable[[str], None] | None,
    on_status: Callable[[str], None] | None,
    step: int,
    total: int,
    label: str,
) -> None:
    if on_status:
        on_status(f"[{step}/{total}] {label}")
    if on_output:
        on_output("")
        on_output(f"[bold #c9a227][{step}/{total}][/bold #c9a227] {label}")


def _run(
    cmd: list[str],
    cwd: Path,
    *,
    timeout: int = 600,
    max_timeout: int | None = None,
    on_output: Callable[[str], None] | None = None,
) -> DeployStep:
    """Run a subprocess, streaming stdout.

    ``timeout`` is an *idle* limit: the process is killed only after this many
    seconds without any output (so long-running pulls keep going while Docker
    prints progress).  ``max_timeout``, when set, is an absolute ceiling.
    """
    if on_output:
        on_output(f"[dim]$ {format_shell_command(cmd, cwd=cwd)}[/dim]")

    lines: list[str] = []
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        step = DeployStep(command=shlex.join(cmd), returncode=127, stdout="", stderr="command not found")
        if on_output:
            on_output("[red]command not found[/red]")
        return step

    assert proc.stdout is not None
    start = time.monotonic()
    last_output = start
    timed_out = False

    for raw in proc.stdout:
        now = time.monotonic()
        if now - last_output > timeout:
            timed_out = True
            proc.kill()
            break
        if max_timeout is not None and now - start > max_timeout:
            timed_out = True
            proc.kill()
            break
        line = raw.rstrip("\n\r")
        lines.append(line)
        last_output = time.monotonic()
        if on_output and line.strip():
            on_output(f"  {line}")

    if not timed_out:
        proc.wait()
    else:
        proc.wait()

    stdout = "\n".join(lines)
    if timed_out:
        step = DeployStep(command=shlex.join(cmd), returncode=124, stdout=stdout, stderr="timed out")
        if on_output:
            on_output("[red]✗ timed out[/red]")
        return step

    step = DeployStep(
        command=shlex.join(cmd),
        returncode=proc.returncode or 0,
        stdout=stdout,
        stderr="",
    )
    if on_output:
        if step.ok:
            on_output("[green]✓ done[/green]")
        else:
            err = stdout.splitlines()[-1] if stdout else f"exit {step.returncode}"
            on_output(f"[red]✗ failed ({err})[/red]")
    return step


def _wait_for_ollama(
    compose: list[str],
    cwd: Path,
    *,
    timeout: int = 180,
    on_output: Callable[[str], None] | None = None,
) -> bool:
    """Poll until the Ollama daemon inside the stack accepts API requests."""
    deadline = time.monotonic() + timeout
    attempt = 0
    probe = [*compose, "exec", "-T", "ollama", "ollama", "list"]
    while time.monotonic() < deadline:
        attempt += 1
        if on_output and attempt == 1:
            on_output(f"[dim]$ {format_shell_command(probe, cwd=cwd)}[/dim]")
        try:
            result = subprocess.run(
                probe,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=30,
            )
        except (subprocess.TimeoutExpired, OSError):
            result = None
        if result is not None and result.returncode == 0:
            if on_output:
                on_output("[green]✓ Ollama server ready[/green]")
            return True
        if on_output:
            on_output(f"[dim]  waiting for Ollama server... ({attempt})[/dim]")
        time.sleep(3)
    if on_output:
        on_output("[red]✗ Ollama server did not become ready in time[/red]")
    return False


def _wait_for_tunnel_url(
    *,
    container_name: str,
    timeout: int = 90,
    on_output: Callable[[str], None] | None = None,
) -> str | None:
    """Read Cloudflare quick-tunnel URL from container logs."""
    logs_cmd = ["docker", "logs", container_name]
    if on_output:
        on_output(f"[dim]$ {format_shell_command(logs_cmd)}[/dim]")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            result = subprocess.run(
                logs_cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
            match = _TUNNEL_URL_RE.search(result.stdout + result.stderr)
            if match:
                return match.group(0)
        except (subprocess.TimeoutExpired, OSError):
            pass
        time.sleep(3)
    return None


def deploy(
    config: SetupConfig,
    *,
    pull: bool = True,
    on_output: Callable[[str], None] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> DeployResult:
    """Start the generated stack with docker compose."""
    config = normalize_access(config.model_copy(deep=True))
    out_dir = Path(config.output_dir).resolve()
    compose_file = out_dir / "docker-compose.yaml"
    if not compose_file.exists():
        return DeployResult(success=False, error=f"Missing {compose_file}")

    if on_output:
        on_output(f"[#c9a227]deploy[/] · {out_dir}")

    compose = _compose_cmd(out_dir, config=config)
    steps: list[DeployStep] = []
    ollama_models = [fc.model.name for fc in config.frameworks if fc.framework == Framework.OLLAMA]
    total = (1 if pull else 0) + 1 + (1 if ollama_models else 0) + len(ollama_models)
    step_no = 0

    if pull:
        step_no += 1
        _announce(on_output, on_status, step_no, total, "Pulling Docker images")
        step = _run(
            [*compose, "pull"],
            out_dir,
            timeout=300,
            max_timeout=7200,
            on_output=on_output,
        )
        steps.append(step)
        if not step.ok:
            _record_run(out_dir, "deploy", steps, on_output)
            return DeployResult(success=False, steps=steps, error=step.stderr or step.stdout or "docker compose pull failed")

    step_no += 1
    _announce(on_output, on_status, step_no, total, "Starting containers (docker compose up -d)")
    step = _run([*compose, "up", "-d"], out_dir, on_output=on_output)
    steps.append(step)
    if not step.ok:
        _record_run(out_dir, "deploy", steps, on_output)
        return DeployResult(success=False, steps=steps, error=step.stderr or step.stdout or "docker compose up failed")

    if ollama_models:
        step_no += 1
        _announce(on_output, on_status, step_no, total, "Waiting for Ollama server")
        if not _wait_for_ollama(compose, out_dir, on_output=on_output):
            _record_run(out_dir, "deploy", steps, on_output)
            return DeployResult(
                success=False,
                steps=steps,
                error="Ollama server did not become ready in time",
            )

    for model_name in ollama_models:
        step_no += 1
        _announce(on_output, on_status, step_no, total, f"Pulling Ollama model: {model_name}")
        pull_cmd = [*compose, "exec", "-T", "ollama", "ollama", "pull", model_name]
        step = _run(pull_cmd, out_dir, timeout=300, max_timeout=7200, on_output=on_output)
        steps.append(step)
        if not step.ok:
            _record_run(out_dir, "deploy", steps, on_output)
            return DeployResult(
                success=False,
                steps=steps,
                error=step.stderr or step.stdout or f"failed to pull ollama model {model_name}",
            )

    if on_status:
        on_status("Deploy complete")

    config = apply_compose_ports(config, out_dir)
    access_urls = build_access_urls(config)
    tunnel_url: str | None = None
    if config.nginx.enabled and config.nginx.tunnel_enabled:
        if on_status:
            on_status("Waiting for public tunnel URL...")
        if on_output:
            on_output("[dim]  waiting for Cloudflare tunnel...[/dim]")
        tunnel_url = _wait_for_tunnel_url(
            container_name=tunnel_container_name(config),
            on_output=on_output,
        )
        if tunnel_url:
            access_urls = enrich_access_urls(config, access_urls, tunnel_url=tunnel_url)
            if on_output:
                on_output(f"[green]✓ Public URL:[/green] {tunnel_url}")
        elif on_output:
            on_output("[yellow]warn:[/yellow] tunnel container started but URL not found in logs")

    if tunnel_url or config.nginx.enabled:
        try:
            from local_llm_setup.urls import render_access_md

            access_md = render_access_md(config, access_urls)
            (out_dir / "ACCESS.md").write_text(access_md, encoding="utf-8")
        except OSError:
            pass

    if on_output:
        on_output("")
        on_output("[bold green]✓ All steps completed[/bold green]")
        for line in format_access_lines(access_urls):
            on_output(line)

    _record_run(out_dir, "deploy", steps, on_output)
    return DeployResult(success=True, steps=steps, access_urls=access_urls)


def stop_stack(
    output_dir: Path,
    *,
    config: SetupConfig | None = None,
    remove_volumes: bool = False,
    on_output: Callable[[str], None] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> DeployResult:
    """Stop the generated Docker Compose stack."""
    out_dir = Path(output_dir).resolve()
    compose_file = out_dir / "docker-compose.yaml"
    if not compose_file.exists():
        return DeployResult(success=False, error=f"Missing {compose_file}")

    if on_output:
        on_output(f"[#c9a227]stop[/] · {out_dir}")

    containers = container_names_from_compose(compose_file)
    if containers and not any_container_running(containers):
        if on_output:
            on_output("[dim]No running containers for this stack.[/dim]")
        return DeployResult(success=True, steps=[])

    steps: list[DeployStep] = []
    total = 2
    step_no = 0
    stopped = False

    for project in compose_project_candidates(out_dir, config):
        compose = _compose_cmd(out_dir, config=config, project=project)
        step_no += 1
        if step_no == 1:
            _announce(on_output, on_status, step_no, total, f"Checking containers (project {project})")
        ps_step = _run([*compose, "ps"], out_dir, timeout=60, on_output=on_output)
        steps.append(ps_step)

        label = (
            "Stopping containers (docker compose down -v)"
            if remove_volumes
            else "Stopping containers (docker compose down)"
        )
        if step_no == 1:
            _announce(on_output, on_status, 2, total, label)
        down_cmd = [*compose, "down"]
        if remove_volumes:
            down_cmd.append("-v")
        step = _run(down_cmd, out_dir, timeout=120, on_output=on_output)
        steps.append(step)
        if step.ok and (not containers or not any_container_running(containers)):
            stopped = True
            break

    if not stopped and containers and any_container_running(containers):
        if on_output:
            on_output("[yellow]compose down missed containers — stopping by name[/yellow]")
        steps.extend(
            _stop_containers_by_name(
                containers,
                remove_volumes=remove_volumes,
                on_output=on_output,
            )
        )
        stopped = not any_container_running(containers)

    if not stopped:
        _record_run(out_dir, "stop", steps, on_output)
        return DeployResult(
            success=False,
            steps=steps,
            error="Could not stop all containers for this stack",
        )

    if on_status:
        on_status("Stack stopped")
    if on_output:
        on_output("")
        on_output("[bold green]✓ Stack stopped[/bold green]")

    _record_run(out_dir, "stop", steps, on_output)
    return DeployResult(success=True, steps=steps)


def stop_all_stacks(
    *,
    remove_volumes: bool = False,
    on_output: Callable[[str], None] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> DeployResult:
    """Stop every running instance."""
    from local_llm_setup.profiles import load_profile

    running = list_running_instances()
    if not running:
        if on_output:
            on_output("[dim]No running stacks to stop.[/dim]")
        return DeployResult(success=True, steps=[])

    if on_output:
        on_output(f"[#c9a227]stop all[/] · {len(running)} instance(s)")

    steps: list[DeployStep] = []
    errors: list[str] = []
    for inst in running:
        config = None
        if inst.profile_path.is_file():
            try:
                config = load_profile(inst.profile_path)
            except OSError:
                config = None
        if on_output:
            on_output(f"\n[bold #c9a227]→ {inst.profile_name}[/bold #c9a227]")
        result = stop_stack(
            inst.output_dir,
            config=config,
            remove_volumes=remove_volumes,
            on_output=on_output,
            on_status=on_status,
        )
        steps.extend(result.steps)
        if not result.success:
            errors.append(f"{inst.profile_name}: {result.error or 'stop failed'}")

    if errors:
        return DeployResult(success=False, steps=steps, error="; ".join(errors))
    return DeployResult(success=True, steps=steps)


def _runtime_test_commands(config: SetupConfig) -> list[str]:
    """Build curl probes on localhost using ports already synced from compose."""
    out_dir = Path(config.output_dir).resolve()
    port = config.nginx.listen_port if config.nginx.enabled else config.frameworks[0].port
    return build_curl_test_commands(config, host="127.0.0.1", port=port, output_dir=out_dir)


def run_curl_tests(
    config: SetupConfig,
    *,
    on_output: Callable[[str], None] | None = None,
    on_status: Callable[[str], None] | None = None,
) -> DeployResult:
    """Run generated curl test commands against the running stack."""
    out_dir = Path(config.output_dir).resolve()
    config = apply_compose_ports(normalize_access(config.model_copy(deep=True)), out_dir)
    urls = build_access_urls(config)
    test_commands = _runtime_test_commands(config)
    if not test_commands:
        return DeployResult(success=False, error="No curl test commands available")

    if on_output:
        on_output("[#c9a227]curl test[/] · checking endpoints")
    if on_status:
        on_status("Running curl tests...")

    steps: list[DeployStep] = []
    for i, cmd in enumerate(test_commands, start=1):
        if on_output:
            on_output("")
            on_output(f"[bold #c9a227][{i}/{len(test_commands)}][/bold #c9a227] curl test")
            on_output(f"[dim]$ {cmd}[/dim]")
        try:
            result = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except FileNotFoundError:
            return DeployResult(success=False, steps=steps, error="curl not found")
        except subprocess.TimeoutExpired:
            step = DeployStep(command=cmd, returncode=124, stdout="", stderr="timed out")
            steps.append(step)
            if on_output:
                on_output("[red]✗ timed out[/red]")
            out_dir = Path(config.output_dir).resolve()
            _record_run(out_dir, "curl-test", steps, on_output)
            return DeployResult(success=False, steps=steps, error=f"curl timed out: {cmd}")

        step = DeployStep(
            command=cmd,
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )
        steps.append(step)
        if on_output:
            body = (result.stdout or result.stderr or "").strip()
            preview = body[:400] + ("…" if len(body) > 400 else "")
            if step.ok:
                on_output(f"[green]✓ HTTP {result.returncode}[/green]")
                if preview:
                    on_output(f"  [dim]{preview}[/dim]")
            else:
                on_output(f"[red]✗ exit {result.returncode}[/red]")
                if preview:
                    on_output(f"  [red]{preview}[/red]")
                out_dir = Path(config.output_dir).resolve()
                _record_run(out_dir, "curl-test", steps, on_output)
                return DeployResult(
                    success=False,
                    steps=steps,
                    error=f"curl failed: {cmd}",
                    access_urls=urls,
                )

    if on_status:
        on_status("All curl tests passed")
    if on_output:
        on_output("")
        on_output("[bold green]✓ All curl tests passed[/bold green]")

    out_dir = Path(config.output_dir).resolve()
    _record_run(out_dir, "curl-test", steps, on_output)
    return DeployResult(success=True, steps=steps, access_urls=urls)
