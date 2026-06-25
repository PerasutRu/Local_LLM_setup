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
from local_llm_setup.profiles import load_profile, save_profile
from local_llm_setup.renderers import generate

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
    output: Path = typer.Option(Path("./output"), "--output", "-o", help="Output directory"),
    profile: Optional[Path] = typer.Option(None, "--profile", "-p", help="Load profile YAML"),
) -> None:
    """Launch interactive TUI wizard."""
    from local_llm_setup.tui.app import run_tui

    initial = load_profile(profile) if profile else None
    if initial:
        initial.output_dir = output
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
    if host.gpu_name:
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
    output: Path = typer.Option(Path("./output"), "--output", "-o"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate only, do not write files"),
) -> None:
    """Generate docker-compose and configs from a profile."""
    setup = load_profile(config)
    setup.output_dir = output
    try:
        result = generate(setup, dry_run=dry_run)
    except ValueError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(1) from exc

    if dry_run:
        console.print("[green]Validation passed (dry run).[/green]")
    else:
        console.print(f"[green]Generated files in {output.resolve()}[/green]")

    for w in result.warnings:
        console.print(f"[yellow]Warning:[/yellow] {w}")

    console.print("\n[bold]Run commands:[/bold]")
    for cmd in result.run_commands:
        console.print(f"  {cmd}")


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
