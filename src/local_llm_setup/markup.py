"""Shared Rich markup helpers for CLI and TUI output."""

from __future__ import annotations

import re

HEADING = "[bold #ffe566]"
LINK = "[bold underline #79c0ff]"
GOLD = "[#c9a227]"
DIM = "[dim]"
END = "[/]"

_URL_RE = re.compile(r"https?://[^\s)\]>]+")


def style_heading(text: str, *, markup: bool = True) -> str:
    if not markup:
        return text
    return f"{HEADING}{text}{END}"


def style_url(url: str, *, markup: bool = True) -> str:
    if not markup:
        return url
    return f"{LINK}{url}{END}"


def style_section(text: str) -> str:
    return f"{HEADING}{text}{END}"


def linkify_text(text: str) -> str:
    """Highlight URLs embedded in footer or status strings."""

    def repl(match: re.Match[str]) -> str:
        return f"{LINK}{match.group(0)}{END}"

    return _URL_RE.sub(repl, text)


def format_log_markdown(raw: str, plain: str) -> str:
    """Convert log lines to Markdown for syntax-highlighted OutputLog."""
    stripped = plain.strip()
    if not stripped:
        return ""

    if stripped in ("Commands executed", "Access URLs"):
        return f"\n## {stripped}"
    if stripped.startswith("Copy-paste to replay"):
        return "\n## Copy-paste to replay"
    if re.fullmatch(r"\[\d+/\d+\] curl test", stripped):
        return f"\n### {stripped}"
    if stripped.startswith("✓ All curl tests passed") or stripped.startswith("✓ Deploy complete"):
        return f"**{stripped}**"
    if stripped.startswith("$ ") or (
        "curl " in stripped and "://" in stripped and not stripped.startswith("  ")
    ):
        return f"```bash\n{stripped}\n```"
    if stripped.startswith("  ") and ("curl " in stripped or stripped.startswith("cd ")):
        return f"```bash\n{stripped.strip()}\n```"

    match = _URL_RE.search(plain)
    if match:
        url = match.group(0)
        prefix = plain[: match.start()].rstrip()
        if prefix.endswith(":"):
            label = prefix.rstrip(":").strip()
            return f"- **{label}:** [{url}]({url})"
        if prefix:
            return f"- {prefix} [{url}]({url})"
        return f"[{url}]({url})"

    return plain
