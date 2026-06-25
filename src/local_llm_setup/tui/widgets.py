"""Reusable TUI widgets."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.dom import DOMNode
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static


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
