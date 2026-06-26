"""Tests for copy-friendly TUI output log."""

from __future__ import annotations

from local_llm_setup.tui.widgets import CopyableRichLog, _plain_markup


def test_plain_markup_strips_rich_tags() -> None:
    assert _plain_markup("[green]✓[/green] ok") == "✓ ok"
    assert _plain_markup("[bold #c9a227][1/3][/bold #c9a227] curl test") == "[1/3] curl test"


def test_plain_markup_passthrough_without_tags() -> None:
    assert _plain_markup("curl -sSf http://127.0.0.1:8080/health") == (
        "curl -sSf http://127.0.0.1:8080/health"
    )


def test_log_hint_constants_mention_copy_keys() -> None:
    from local_llm_setup.tui.widgets import LOG_FOOTER_HINT, LOG_HINT_COPY, LOG_HINT_PRETTY

    assert "c" in LOG_HINT_PRETTY
    assert "Ctrl+C" in LOG_HINT_COPY
    assert "copy mode" in LOG_FOOTER_HINT


def test_copyable_rich_log_keeps_plain_buffer() -> None:
    log = CopyableRichLog()
    log.write("[green]✓[/green] ok")
    log.write("[bold underline #79c0ff]http://127.0.0.1:8080[/]")
    assert log.plain_text() == "✓ ok\nhttp://127.0.0.1:8080"
    assert len(log._pending_rich_lines) == 2
