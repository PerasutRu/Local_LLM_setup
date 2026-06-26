"""Slash commands for the TUI command bar."""

from __future__ import annotations

from dataclasses import dataclass

from local_llm_setup.models.config import Framework


@dataclass(frozen=True)
class SlashCommand:
    name: str
    description: str
    aliases: tuple[str, ...] = ()


SLASH_COMMANDS: tuple[SlashCommand, ...] = (
    SlashCommand("help", "แสดงคำสั่งทั้งหมด"),
    SlashCommand("instances", "ดู/เลือก profile — แก้ไข, deploy, stop", aliases=("profiles", "list")),
    SlashCommand("providers", "เลือก provider (ollama, vllm, …)"),
    SlashCommand("deploy", "generate และ start stack จาก profile ปัจจุบัน"),
    SlashCommand("stop", "หยุด stack — เลือก instance หรือหยุดทั้งหมด (/stop ชื่อ)"),
    SlashCommand("delete-container", "หยุดและลบ containers + volumes", aliases=("delete",)),
    SlashCommand("test", "รัน curl test กับ stack ที่รันอยู่", aliases=("curl",)),
    SlashCommand("doctor", "กลับไปหน้า Host Doctor"),
)

PROVIDER_CHOICES: tuple[tuple[str, str], ...] = (
    (Framework.OLLAMA.value, "Ollama — easy local models"),
    (Framework.VLLM.value, "vLLM — OpenAI-compatible (NVIDIA GPU)"),
)


def command_placeholder() -> str:
    """Short hint shown in the command input."""
    names = [f"/{sc.name}" for sc in SLASH_COMMANDS[:5]]
    return " · ".join(names) + " · /help"


def parse_command(text: str) -> tuple[str, list[str]]:
    """Parse '/stop smollm-1' into ('stop', ['smollm-1'])."""
    cmd = text.strip().lower()
    if cmd.startswith("/"):
        cmd = cmd[1:]
    parts = cmd.split()
    if not parts:
        return "", []
    return parts[0], parts[1:]


def normalize_command(text: str) -> str:
    """Parse '/providers' or 'providers' into 'providers'."""
    name, _ = parse_command(text)
    return name


@dataclass(frozen=True)
class CommandMatch:
    canonical: str
    display: str
    description: str


def _command_matches() -> list[CommandMatch]:
    rows: list[CommandMatch] = []
    seen: set[str] = set()
    for sc in SLASH_COMMANDS:
        if sc.name not in seen:
            seen.add(sc.name)
            rows.append(CommandMatch(sc.name, f"/{sc.name}", sc.description))
        for alias in sc.aliases:
            if alias not in seen:
                seen.add(alias)
                rows.append(CommandMatch(sc.name, f"/{alias}", sc.description))
    return rows


def match_commands(query: str) -> list[CommandMatch]:
    """Filter slash commands by partial input."""
    name, _ = parse_command(query)
    if not name and not query.strip():
        return _command_matches()
    token = name or query.strip().lstrip("/").lower()
    matches = [
        row
        for row in _command_matches()
        if row.canonical.startswith(token) or row.display.lstrip("/").startswith(token)
    ]
    if matches:
        return matches
    if query.strip().startswith("/") or not query.strip():
        return _command_matches()
    return []


def format_suggestions(query: str, *, selected: int = 0) -> list[str]:
    """Rich markup lines for the suggestion panel."""
    matches = match_commands(query)
    if not matches:
        return []
    lines = ["[dim]Slash commands[/dim]"]
    for index, row in enumerate(matches[:10]):
        mark = "[bold #ffe566]›[/bold #ffe566]" if index == selected else " "
        desc = row.description if index == selected else f"[dim]{row.description}[/dim]"
        lines.append(f" {mark} [#c9a227]{row.display}[/] — {desc}")
    lines.append("[dim]Tab autocomplete · ↑↓ select · Enter run[/dim]")
    return lines


def selected_match(query: str, selected: int) -> CommandMatch | None:
    matches = match_commands(query)
    if not matches:
        return None
    return matches[min(max(selected, 0), len(matches) - 1)]


def format_help_lines() -> list[str]:
    lines = ["[bold #c9a227]Slash commands[/bold #c9a227]"]
    for sc in SLASH_COMMANDS:
        alias = f" (/{', /'.join(sc.aliases)})" if sc.aliases else ""
        lines.append(f"  /{sc.name}{alias} — {sc.description}")
    lines.append("")
    lines.append("[dim]กด / เพื่อโฟกัส command bar · Tab autocomplete · Enter เพื่อรัน[/dim]")
    return lines
