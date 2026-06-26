"""Tests for Rich markup helpers."""

from __future__ import annotations

from local_llm_setup.markup import format_log_markdown, linkify_text, style_heading, style_url


def test_style_url_uses_link_color() -> None:
    assert "#79c0ff" in style_url("http://127.0.0.1:8080")


def test_style_heading_uses_heading_color() -> None:
    assert "#ffe566" in style_heading("Access URLs")


def test_linkify_text_wraps_urls() -> None:
    text = linkify_text("Ready · http://127.0.0.1:8080")
    assert "#79c0ff" in text
    assert "http://127.0.0.1:8080" in text


def test_format_log_markdown_headings_and_links() -> None:
    assert format_log_markdown("[bold]Access URLs[/bold]", "Access URLs") == "\n## Access URLs"
    md = format_log_markdown("", "  local:   http://127.0.0.1:8080")
    assert "http://127.0.0.1:8080" in md
    assert "**local:**" in md
