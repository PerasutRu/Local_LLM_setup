"""Tests for TUI slash command suggestions."""

from __future__ import annotations

from local_llm_setup.tui.commands import (
    format_suggestions,
    match_commands,
    match_commands_for_tab,
    parse_command,
    resolve_submit_command,
    selected_match,
)


def test_parse_command_with_args():
    assert parse_command("/stop smollm-1") == ("stop", ["smollm-1"])
    assert parse_command("deploy") == ("deploy", [])


def test_match_commands_filters():
    matches = match_commands("/st")
    names = {m.canonical for m in matches}
    assert "stop" in names


def test_match_commands_name_only_not_aliases():
    assert [m.canonical for m in match_commands("/pro")] == ["providers"]
    assert "instances" not in {m.canonical for m in match_commands("/p")}
    assert match_commands("/profiles") == []
    assert match_commands("/curl") == []


def test_match_commands_no_duplicate_aliases():
    matches = match_commands("/")
    displays = [m.display for m in matches]
    assert displays.count("/instances") == 1
    assert "/profiles" not in displays
    assert "/list" not in displays


def test_match_commands_hidden_without_slash():
    assert match_commands("") == []
    assert match_commands("help") == []
    assert match_commands("/") != []


def test_format_suggestions_highlights_keyboard_selection():
    lines = format_suggestions("/de", selected=1)
    assert lines[2].startswith(" [bold #ffe566]›[/bold #ffe566]")
    assert "/deploy" in lines[2]


def test_format_suggestions_includes_description():
    lines = format_suggestions("/stop", selected=0)
    text = "\n".join(lines)
    assert "/stop" in text
    assert "หยุด" in text


def test_match_commands_multiple_prefix_matches():
    names = [m.canonical for m in match_commands("/de")]
    assert names == ["delete-profile", "deploy", "delete-container"]


def test_selected_match():
    row = selected_match("/inst", 0)
    assert row is not None
    assert row.canonical == "instances"


def test_resolve_submit_command_uses_keyboard_selection():
    assert resolve_submit_command("/", 2) == f"/{match_commands('/')[2].canonical}"
    assert resolve_submit_command("/dep", 0) == "/deploy"
    assert resolve_submit_command("/de", 1) == "/deploy"
    assert resolve_submit_command("/de", 2) == "/delete-container"


def test_resolve_submit_command_keeps_args():
    assert resolve_submit_command("/stop smollm-1", 0) == "/stop smollm-1"


def test_resolve_submit_command_exact_typed_command():
    assert resolve_submit_command("/help", 0) == "/help"


def test_match_commands_for_tab_matches_suggestion_list():
    assert match_commands_for_tab("/pro") == match_commands("/pro")
    assert match_commands_for_tab("/") == []
