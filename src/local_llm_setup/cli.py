"""CLI entrypoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from local_llm_setup import __version__
from local_llm_setup.detect import detect_host, run_doctor
from local_llm_setup.models.config import SetupConfig
from local_llm_setup.paths import OUTPUT_DIR, normalize_output_dir
from local_llm_setup.profiles import load_profile, save_profile
from local_llm_setup.instances import list_instances
from local_llm_setup.renderers import generate
from local_llm_setup.runner import deploy, stop_all_stacks, stop_stack
from local_llm_setup.urls import build_access_urls, format_access_lines

app = typer.Typer(
    name="local-llm-setup",
    help="TUI wizard for hosting local LLMs with Docker.",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main_version(
    version: bool = typer.Option(False, "--version", "-V", help="Show version"),
) -> None:
    if version:
        console.print(f"local-llm-setup {__version__}")
        raise typer.Exit()


@app.command()
def tui(
    output: Path = typer.Option(OUTPUT_DIR, "--output", "-o", help="Output directory"),
    profile: Optional[Path] = typer.Option(None, "--profile", "-p", help="Load profile YAML"),
) -> None:
    """Launch interactive TUI wizard."""
    from local_llm_setup.tui.app import run_tui

    initial = load_profile(profile) if profile else None
    if initial:
        initial.output_dir = normalize_output_dir(initial.profile_name, initial.output_dir)
        output = initial.output_dir
    run_tui(output_dir=output, initial_config=initial)


@app.command()
def doctor(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Check host dependencies (Docker, GPU, CUDA, nginx)."""
    host = run_doctor()
    if json_output:
        console.print_json(host.model_dump_json(indent=2))
        return

    console.print(f"\n[bold]Host:[/bold] {host.os_type.value} {host.os_version} ({host.arch})")
    if host.is_wsl:
        console.print("[dim]Running in WSL[/dim]")
    if host.gpu_devices:
        for device in host.gpu_devices:
            console.print(
                f"[bold]GPU {device.index}:[/bold] {device.name} ({device.vram_gb or '?'} GB VRAM)"
            )
    elif host.gpu_name:
        console.print(f"[bold]GPU:[/bold] {host.gpu_name} ({host.vram_gb or '?'} GB VRAM)")
    if host.ram_gb:
        console.print(f"[bold]RAM:[/bold] {host.ram_gb} GB")

    table = Table(title="Doctor Checks")
    table.add_column("Check", style="cyan")
    table.add_column("Status")
    table.add_column("Message")
    table.add_column("Hint", style="dim")

    status_style = {"ok": "green", "warn": "yellow", "fail": "red", "skip": "dim"}
    for check in host.checks:
        style = status_style.get(check.status.value, "white")
        table.add_row(
            check.name,
            f"[{style}]{check.status.value.upper()}[/{style}]",
            check.message,
            check.hint or "",
        )
    console.print(table)


@app.command()
def detect() -> None:
    """Detect OS and hardware (alias for doctor)."""
    doctor(json_output=False)


@app.command("generate")
def generate_cmd(
    config: Path = typer.Option(..., "--config", "-c", help="Profile YAML path"),
    output: Path = typer.Option(OUTPUT_DIR, "--output", "-o"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate only, do not write files"),
    run_after: bool = typer.Option(False, "--run", help="Start Docker after generating"),
    no_pull: bool = typer.Option(False, "--no-pull", help="Skip docker compose pull when using --run"),
) -> None:
    """Generate docker-compose and configs from a profile."""
    setup = load_profile(config)
    setup.output_dir = normalize_output_dir(setup.profile_name, output if output != OUTPUT_DIR else setup.output_dir)
    try:
        result = generate(setup, dry_run=dry_run)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if dry_run:
        console.print("[green]Validation passed (dry run).[/green]")
    else:
        console.print(f"[green]Generated files in {setup.output_dir.resolve()}[/green]")

    for w in result.warnings:
        console.print(f"[yellow]Warning:[/yellow] {w}")

    if run_after and not dry_run:
        console.print("\n[bold]Deploying with Docker...[/bold]")
        deploy_config = result.config or setup
        deploy_result = deploy(
            deploy_config,
            pull=not no_pull,
            on_output=lambda line: console.print(line),
            on_status=lambda msg: console.print(f"[cyan]→ {msg}[/cyan]"),
        )
        if deploy_result.success:
            console.print("[green]Docker stack is running.[/green]")
            if deploy_result.access_urls:
                console.print("\n[bold]Access URLs:[/bold]")
                for line in format_access_lines(deploy_result.access_urls, markup=False):
                    if line.strip():
                        console.print(f"  {line.strip()}")
        else:
            console.print(f"[red]Deploy failed:[/red] {deploy_result.error}")
            raise typer.Exit(1)
        return

    console.print("\n[bold]Commands to run:[/bold]")
    for cmd in result.run_commands:
        console.print(f"  [dim]$[/dim] {cmd}")
    urls = build_access_urls(setup)
    console.print("\n[bold]Access URLs (after deploy):[/bold]")
    for line in format_access_lines(urls, markup=False):
        if line.strip():
            console.print(f"  {line.strip()}")


@app.command()
def run(
    config: Path = typer.Option(..., "--config", "-c", help="Profile YAML path"),
    output: Path = typer.Option(OUTPUT_DIR, "--output", "-o"),
    no_pull: bool = typer.Option(False, "--no-pull", help="Skip docker compose pull"),
) -> None:
    """Start the generated Docker stack."""
    setup = load_profile(config)
    setup.output_dir = normalize_output_dir(setup.profile_name, output if output != OUTPUT_DIR else setup.output_dir)
    compose_file = setup.output_dir / "docker-compose.yaml"
    if not compose_file.exists():
        console.print(f"[red]Missing {compose_file}[/red] — run generate first.")
        raise typer.Exit(1)

    console.print(f"[bold]Deploying from {setup.output_dir.resolve()}...[/bold]")
    result = deploy(
        setup,
        pull=not no_pull,
        on_output=lambda line: console.print(line),
        on_status=lambda msg: console.print(f"[cyan]→ {msg}[/cyan]"),
    )
    if result.success:
        console.print("[green]Docker stack is running.[/green]")
        if result.access_urls:
            console.print("\n[bold]Access URLs:[/bold]")
            for line in format_access_lines(result.access_urls, markup=False):
                if line.strip():
                    console.print(f"  {line.strip()}")
    else:
        console.print(f"[red]Deploy failed:[/red] {result.error}")
        raise typer.Exit(1)


@app.command()
def stop(
    output: Path = typer.Option(OUTPUT_DIR, "--output", "-o", help="Output directory with docker-compose.yaml"),
    config: Optional[Path] = typer.Option(None, "--config", "-c", help="Profile YAML (uses its output_dir if set)"),
    all_instances: bool = typer.Option(False, "--all", "-a", help="Stop every running instance"),
    volumes: bool = typer.Option(False, "--volumes", "-v", help="Remove volumes (deletes downloaded models/data)"),
) -> None:
    """Stop the running Docker stack."""
    if all_instances:
        console.print("[bold]Stopping all running stacks...[/bold]")
        result = stop_all_stacks(
            remove_volumes=volumes,
            on_output=lambda line: console.print(line),
            on_status=lambda msg: console.print(f"[cyan]→ {msg}[/cyan]"),
        )
        if result.success:
            console.print("[green]All Docker stacks stopped.[/green]")
        else:
            console.print(f"[red]Stop failed:[/red] {result.error}")
            raise typer.Exit(1)
        return

    setup: SetupConfig | None = None
    if config:
        setup = load_profile(config)
        out = normalize_output_dir(setup.profile_name, setup.output_dir)
    else:
        out = output

    compose_file = out / "docker-compose.yaml"
    if not compose_file.exists():
        console.print(f"[red]Missing {compose_file}[/red] — run generate first or check --output.")
        raise typer.Exit(1)

    console.print(f"[bold]Stopping stack in {out.resolve()}...[/bold]")
    result = stop_stack(
        out,
        config=setup if config else None,
        remove_volumes=volumes,
        on_output=lambda line: console.print(line),
        on_status=lambda msg: console.print(f"[cyan]→ {msg}[/cyan]"),
    )
    if result.success:
        console.print("[green]Docker stack stopped.[/green]")
    else:
        console.print(f"[red]Stop failed:[/red] {result.error}")
        raise typer.Exit(1)


@app.command()
def instances(
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """List saved profiles and their deployment status."""
    rows = list_instances()
    if json_output:
        import json as json_mod

        payload = [
            {
                "profile_name": i.profile_name,
                "status": i.status,
                "output_dir": str(i.output_dir),
                "ports": i.ports,
                "frameworks": i.frameworks,
                "nginx": i.nginx_enabled,
                "tunnel": i.tunnel_enabled,
            }
            for i in rows
        ]
        console.print_json(json_mod.dumps(payload, indent=2))
        return

    if not rows:
        console.print("[dim]No profiles found in llm_local/profiles/[/dim]")
        return

    table = Table(title="Local LLM instances")
    table.add_column("Profile", style="cyan")
    table.add_column("Status")
    table.add_column("Frameworks")
    table.add_column("Ports")
    table.add_column("Output", style="dim")

    status_style = {"running": "green", "stopped": "yellow", "not_deployed": "dim"}
    for inst in rows:
        style = status_style.get(inst.status, "white")
        table.add_row(
            inst.profile_name,
            f"[{style}]{inst.status}[/{style}]",
            ", ".join(inst.frameworks) or "—",
            inst.ports_summary,
            str(inst.output_dir),
        )
    console.print(table)


@app.command()
def save(
    config: Path = typer.Option(..., "--config", "-c"),
    name: str = typer.Option("default", "--name", "-n"),
) -> None:
    """Save a profile YAML from an existing config file."""
    setup = load_profile(config)
    setup.profile_name = name
    path = save_profile(setup)
    console.print(f"[green]Saved profile to {path}[/green]")


if __name__ == "__main__":
    app()
