"""Reusable TUI widgets."""

from __future__ import annotations

from rich.errors import MarkupError
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.dom import DOMNode
from textual.events import Focus
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, RichLog, Static, TextArea


def _plain_markup(line: str) -> str:
    if "[" not in line:
        return line
    try:
        return Text.from_markup(line).plain
    except MarkupError:
        return line


LOG_HINT_PRETTY = (
    "[dim]โหมดสี (Pretty)[/] · log แสดงสีและ link · "
    "กด [bold #ffe566]c[/] → [bold #79c0ff]Copy mode[/] "
    "(ลากเลือกข้อความ · [bold]Ctrl+C[/bold] / [bold]Cmd+C[/bold] copy)"
)
LOG_HINT_COPY = (
    "[bold #79c0ff]Copy mode[/] · ลากเลือกข้อความ · "
    "[bold]Ctrl+C[/bold] / [bold]Cmd+C[/bold] copy · "
    "กด [bold #ffe566]v[/] หรือ [bold]Esc[/] → กลับโหมดสี"
)
LOG_FOOTER_HINT = "c copy mode · v/Esc pretty · s stop · /test · q quit"


class CopyableRichLog(Widget):
    """Colored Rich log with a toggleable plain-text copy mode."""

    DEFAULT_CSS = """
    CopyableRichLog {
        layout: vertical;
        height: 100%;
        min-height: 24;
    }

    CopyableRichLog #log-hint {
        height: auto;
        color: #888888;
        padding: 0 0 1 0;
    }

    CopyableRichLog RichLog {
        height: 1fr;
        min-height: 20;
        border: solid #333333;
        background: #0d0d0d;
        padding: 0 1;
    }

    CopyableRichLog TextArea {
        height: 1fr;
        min-height: 20;
        border: solid #79c0ff;
        background: #0d0d0d;
        display: none;
    }

    CopyableRichLog.-copy-mode RichLog {
        display: none;
    }

    CopyableRichLog.-copy-mode TextArea {
        display: block;
    }
    """

    BINDINGS = [
        Binding("c", "toggle_copy_mode", "Copy mode", show=True),
        Binding("v", "show_pretty_mode", "Pretty view", show=False),
        Binding("escape", "show_pretty_mode", "Pretty view", show=False),
    ]

    copy_mode: reactive[bool] = reactive(False)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._plain_lines: list[str] = []
        self._pending_rich_lines: list[str] = []

    def compose(self) -> ComposeResult:
        yield Static(LOG_HINT_PRETTY, id="log-hint")
        yield RichLog(highlight=True, markup=True, wrap=True, id="rich-log")
        yield TextArea(
            read_only=True,
            show_cursor=False,
            show_line_numbers=False,
            soft_wrap=True,
            tab_behavior="indent",
            id="copy-log",
        )

    def on_mount(self) -> None:
        self.can_focus = True
        self._update_mode_hint()
        rich_log = self.query_one("#rich-log", RichLog)
        for line in self._pending_rich_lines:
            rich_log.write(line)
        self._pending_rich_lines.clear()
        if self.copy_mode:
            self._sync_copy_view()

    def write(self, line: str) -> None:
        self._plain_lines.append(_plain_markup(line))
        if self.is_attached:
            self.query_one("#rich-log", RichLog).write(line)
            if self.copy_mode:
                self._sync_copy_view()
        else:
            self._pending_rich_lines.append(line)

    def scroll_end(self, *, animate: bool = False) -> None:
        if not self.is_attached:
            return
        self._active_log().scroll_end(animate=animate)

    def clear_log(self) -> None:
        self._plain_lines.clear()
        self._pending_rich_lines.clear()
        if self.is_attached:
            self.query_one("#rich-log", RichLog).clear()
            if self.copy_mode:
                self._sync_copy_view()

    def plain_text(self) -> str:
        return "\n".join(self._plain_lines)

    def _active_log(self) -> RichLog | TextArea:
        if self.copy_mode:
            return self.query_one("#copy-log", TextArea)
        return self.query_one("#rich-log", RichLog)

    def _sync_copy_view(self) -> None:
        if not self.is_attached:
            return
        copy_log = self.query_one("#copy-log", TextArea)
        copy_log.load_text(self.plain_text())
        copy_log.scroll_end(animate=False)

    def _update_mode_hint(self) -> None:
        if not self.is_attached:
            return
        hint = LOG_HINT_COPY if self.copy_mode else LOG_HINT_PRETTY
        self.query_one("#log-hint", Static).update(hint)

    def _watch_copy_mode(self, copy_mode: bool) -> None:
        self.set_class(copy_mode, "-copy-mode")
        self._update_mode_hint()
        if not self.is_attached:
            return
        if copy_mode:
            self._sync_copy_view()
            self.query_one("#copy-log", TextArea).focus()
            self.app.notify("Copy mode — ลากเลือกข้อความ แล้ว Ctrl+C / Cmd+C", timeout=3)
        else:
            self.query_one("#rich-log", RichLog).focus()
            self.app.notify("Pretty view — แสดง log แบบมีสี", timeout=2)

    def action_toggle_copy_mode(self) -> None:
        self.copy_mode = not self.copy_mode

    def action_show_pretty_mode(self) -> None:
        if self.copy_mode:
            self.copy_mode = False

    def action_copy_all(self) -> None:
        text = self.plain_text()
        if not text:
            return
        self.app.copy_to_clipboard(text)
        self.app.notify("Copied log to clipboard", timeout=2)


# Backward-compatible alias for imports/tests.
OutputLog = CopyableRichLog


class ChoiceItem(Static):
    """Single selectable choice row."""

    DEFAULT_CSS = """
    ChoiceItem {
        height: 1;
        padding: 0 1;
    }
    ChoiceItem.selected {
        background: #2a2a00;
        color: #ffe566;
    }
ChoiceItem.checked {
    color: #3ecf3e;
}
    """

    def __init__(self, choice_id: str, label: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.choice_id = choice_id
        self.choice_label = label
        self.selected = False
        self.checked = False

    def render(self) -> str:
        if self.checked:
            mark = "[bold #3ecf3e]✓[/]"
        else:
            mark = " "
        prefix = "›" if self.selected else " "
        label = f"[#3ecf3e]{self.choice_label}[/]" if self.checked else self.choice_label
        return f"  {prefix} {mark} {label}"

    def set_selected(self, value: bool) -> None:
        self.selected = value
        self.refresh()

    def toggle_checked(self) -> None:
        self.checked = not self.checked
        self.refresh()


class ChoiceList(Widget):
    """Keyboard-navigable choice list. Space toggles, Enter confirms."""

    DEFAULT_CSS = """
    ChoiceList {
        height: auto;
        padding: 0;
    }
    """

    BINDINGS = [
        Binding("up", "cursor_up", "Up", show=False),
        Binding("down", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("j", "cursor_down", "Down", show=False),
        Binding("space", "toggle", "Select", show=False),
        Binding("enter", "submit", "Confirm", show=False),
    ]

    class Submitted(Message):
        def __init__(self, sender: ChoiceList, selected_ids: list[str], multi: bool) -> None:
            super().__init__()
            self._choice_list = sender
            self.selected_ids = selected_ids
            self.multi = multi

        @property
        def control(self) -> DOMNode | None:
            return self._choice_list

    def __init__(
        self,
        choices: list[tuple[str, str]],
        *,
        multi: bool = False,
        allow_empty: bool = False,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self._choices = choices
        self.multi = multi
        self.allow_empty = allow_empty
        self._index = 0
        self._items: list[ChoiceItem] = []

    def compose(self) -> ComposeResult:
        for cid, label in self._choices:
            item = ChoiceItem(cid, label)
            self._items.append(item)
            yield item
        if self._items:
            self._items[0].set_selected(True)

    def on_mount(self) -> None:
        self.can_focus = True

    def action_cursor_up(self) -> None:
        if not self._items:
            return
        self._items[self._index].set_selected(False)
        self._index = (self._index - 1) % len(self._items)
        self._items[self._index].set_selected(True)

    def action_cursor_down(self) -> None:
        if not self._items:
            return
        self._items[self._index].set_selected(False)
        self._index = (self._index + 1) % len(self._items)
        self._items[self._index].set_selected(True)

    def action_toggle(self) -> None:
        if not self._items:
            return
        if self.multi:
            self._items[self._index].toggle_checked()
        else:
            for i, item in enumerate(self._items):
                item.checked = i == self._index
                item.refresh()

    def action_submit(self) -> None:
        if self.multi:
            ids = [item.choice_id for item in self._items if item.checked]
            if not ids and not self.allow_empty:
                self._items[self._index].toggle_checked()
                ids = [self._items[self._index].choice_id]
        else:
            ids = [self._items[self._index].choice_id]
        self.post_message(self.Submitted(self, ids, self.multi))

    def selected_ids(self) -> list[str]:
        if self.multi:
            return [item.choice_id for item in self._items if item.checked]
        return [self._items[self._index].choice_id] if self._items else []

    def set_checked(self, choice_ids: set[str]) -> None:
        for item in self._items:
            item.checked = item.choice_id in choice_ids
            item.refresh()


class CommandInput(Input):
    """Command bar input with Tab autocomplete for slash commands."""

    class Autocomplete(Message):
        """Request slash command autocomplete."""

        def __init__(self, input_widget: CommandInput) -> None:
            self.input_widget = input_widget
            super().__init__()

    class Focused(Message):
        """Command input received focus."""

        def __init__(self, input_widget: CommandInput) -> None:
            self.input_widget = input_widget
            super().__init__()

    BINDINGS = [
        Binding("tab", "request_autocomplete", "Autocomplete", show=False),
        Binding("enter", "submit_command", "Run command", show=False),
    ]

    def action_submit_command(self) -> None:
        """Submit slash command without the app-level Enter handler stealing focus."""
        self.post_message(Input.Submitted(self, self.value))

    def _on_focus(self, event: Focus) -> None:
        super()._on_focus(event)
        self.post_message(CommandInput.Focused(self))

    def action_request_autocomplete(self) -> None:
        if self.value.strip().startswith("/"):
            self.post_message(CommandInput.Autocomplete(self))
            return
        if self.app is not None:
            self.app.action_focus_next()
