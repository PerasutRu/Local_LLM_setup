"""Tests for TUI slash command suggestions."""

from __future__ import annotations

from local_llm_setup.tui.commands import (
    format_suggestions,
    match_commands,
    parse_command,
    selected_match,
)


def test_parse_command_with_args():
    assert parse_command("/stop smollm-1") == ("stop", ["smollm-1"])
    assert parse_command("deploy") == ("deploy", [])


def test_match_commands_filters():
    matches = match_commands("/st")
    names = {m.canonical for m in matches}
    assert "stop" in names


def test_match_commands_hidden_without_slash():
    assert match_commands("") == []
    assert match_commands("help") == []
    assert match_commands("/") != []


def test_format_suggestions_includes_description():
    lines = format_suggestions("/stop", selected=0)
    text = "\n".join(lines)
    assert "/stop" in text
    assert "หยุด" in text


def test_selected_match():
    row = selected_match("/inst", 0)
    assert row is not None
    assert row.canonical == "instances"
