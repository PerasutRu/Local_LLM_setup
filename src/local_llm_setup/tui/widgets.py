"""Reusable TUI widgets."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Label, Static


class ChoiceItem(Static):
    """Single selectable choice row."""

    DEFAULT_CSS = """
    ChoiceItem {
        height: 1;
        padding: 0 1;
    }
    ChoiceItem.selected {
        background: $accent;
        color: $text;
    }
    ChoiceItem.checked {
        color: $success;
    }
    """

    def __init__(self, choice_id: str, label: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.choice_id = choice_id
        self.choice_label = label
        self.selected = False
        self.checked = False

    def render(self) -> str:
        mark = "[x]" if self.checked else "[ ]"
        prefix = ">" if self.selected else " "
        return f"{prefix} {mark} {self.choice_label}"

    def set_selected(self, value: bool) -> None:
        self.selected = value
        self.refresh()

    def toggle_checked(self) -> None:
        self.checked = not self.checked
        self.refresh()


class ChoiceList(Static):
    """Keyboard-navigable choice list. Space toggles, Enter confirms."""

    DEFAULT_CSS = """
    ChoiceList {
        height: auto;
        border: solid $primary;
        padding: 0 1;
    }
    """

    class Submitted(Message):
        def __init__(self, selected_ids: list[str], multi: bool) -> None:
            super().__init__()
            self.selected_ids = selected_ids
            self.multi = multi

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

    def key_up(self) -> None:
        if not self._items:
            return
        self._items[self._index].set_selected(False)
        self._index = (self._index - 1) % len(self._items)
        self._items[self._index].set_selected(True)

    def key_down(self) -> None:
        if not self._items:
            return
        self._items[self._index].set_selected(False)
        self._index = (self._index + 1) % len(self._items)
        self._items[self._index].set_selected(True)

    def key_space(self) -> None:
        if not self._items:
            return
        if self.multi:
            self._items[self._index].toggle_checked()
        else:
            for i, item in enumerate(self._items):
                item.checked = i == self._index
                item.refresh()

    def key_enter(self) -> None:
        if self.multi:
            ids = [item.choice_id for item in self._items if item.checked]
            if not ids and not self.allow_empty:
                self._items[self._index].toggle_checked()
                ids = [self._items[self._index].choice_id]
        else:
            ids = [self._items[self._index].choice_id]
        self.post_message(self.Submitted(ids, self.multi))

    def selected_ids(self) -> list[str]:
        if self.multi:
            return [item.choice_id for item in self._items if item.checked]
        return [self._items[self._index].choice_id] if self._items else []


class StepPanel(Vertical):
    """Wizard step with title, body, and optional input hint."""

    title: reactive[str] = reactive("")
    hint: reactive[str] = reactive("↑/↓ navigate · Space select · Enter confirm · q quit")

    DEFAULT_CSS = """
    StepPanel {
        height: 1fr;
        padding: 1 2;
    }
    StepPanel #step-title {
        text-style: bold;
        height: 1;
        margin-bottom: 1;
    }
    StepPanel #step-hint {
        dock: bottom;
        height: 1;
        color: $text-muted;
    }
    """

    def __init__(self, title: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.title = title

    def compose(self) -> ComposeResult:
        yield Label(id="step-title")
        yield Label(id="step-hint")

    def watch_title(self, value: str) -> None:
        self.query_one("#step-title", Label).update(value)

    def watch_hint(self, value: str) -> None:
        self.query_one("#step-hint", Label).update(value)
