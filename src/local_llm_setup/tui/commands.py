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
    SlashCommand("providers", "เลือก provider — ollama หรือ vllm"),
    SlashCommand("delete-container", "หยุดและลบ containers + volumes", aliases=("delete",)),
    SlashCommand("stop", "หยุด Docker stack (ไม่ลบ volumes)"),
    SlashCommand("test", "รัน curl test กับ stack ที่รันอยู่", aliases=("curl",)),
    SlashCommand("deploy", "generate และ start stack ใหม่"),
    SlashCommand("doctor", "กลับไปหน้า Host Doctor"),
)

PROVIDER_CHOICES: tuple[tuple[str, str], ...] = (
    (Framework.OLLAMA.value, "Ollama — easy local models"),
    (Framework.VLLM.value, "vLLM — OpenAI-compatible (NVIDIA GPU)"),
)


def normalize_command(text: str) -> str:
    """Parse '/providers' or 'providers' into 'providers'."""
    cmd = text.strip().lower()
    if cmd.startswith("/"):
        cmd = cmd[1:]
    return cmd.split()[0] if cmd else ""


def format_help_lines() -> list[str]:
    lines = ["[bold #c9a227]Slash commands[/bold #c9a227]"]
    for sc in SLASH_COMMANDS:
        alias = f" (/{', /'.join(sc.aliases)})" if sc.aliases else ""
        lines.append(f"  /{sc.name}{alias} — {sc.description}")
    lines.append("")
    lines.append("[dim]กด / เพื่อโฟกัส command bar · Enter เพื่อรัน[/dim]")
    return lines
