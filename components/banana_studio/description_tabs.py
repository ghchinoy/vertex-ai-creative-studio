"""A component for displaying descriptions and questions in a tabbed view."""

from collections.abc import Callable
from dataclasses import dataclass

import mesop as me


@me.stateclass
class State:
    selected_tab_index: int = 0


@dataclass
class Tab:
    label: str
    content: Callable
    selected: bool = False
    disabled: bool = False
    icon: str | None = None


@me.component
def _description_tab_content(description: str):
    me.textarea(
        value=description,
        readonly=True,
        rows=4,
        autosize=True,
        style=me.Style(
            width="100%", font_size="12pt", border=None, background="transparent",
        ),
    )


@me.component
def _questions_tab_content(questions: list[str]):
    with me.box(style=me.Style(display="flex", flex_direction="column", gap=8)):
        for i, question in enumerate(questions):
            me.text(f"{i + 1}. {question}")


def on_tab_click(e: me.ClickEvent):
    """Click handler that handles updating the tabs when clicked."""
    state = me.state(State)
    _, tab_index_str = e.key.split("-")
    tab_index = int(tab_index_str)

    if tab_index == state.selected_tab_index:
        return

    state.selected_tab_index = tab_index


@me.component
def _tab_header(tabs: list[Tab], on_tab_click_handler: Callable):
    """Generates the header for the tab group."""
    with me.box(
        style=me.Style(
            display="flex",
            width="100%",
            border=me.Border(
                bottom=me.BorderSide(
                    width=1, style="solid", color=me.theme_var("outline-variant"),
                ),
            ),
        ),
    ):
        for index, tab in enumerate(tabs):
            with me.box(
                key=f"tab-{index}",
                on_click=on_tab_click_handler,
                style=_make_tab_style(tab.selected, tab.disabled),
            ):
                if tab.icon:
                    me.icon(tab.icon)
                me.text(tab.label)


@me.component
def _tab_content(tabs: list[Tab]):
    """Component for rendering the content of the selected tab."""
    for tab in tabs:
        if tab.selected:
            with me.box(style=me.Style(padding=me.Padding(top=16))):
                tab.content()


def _make_tab_style(selected: bool, disabled: bool) -> me.Style:
    """Makes the styles for the tab based on selected/disabled state."""
    style = _make_default_tab_style()
    if disabled:
        style.color = me.theme_var("outline")
        style.cursor = "default"
    elif selected:
        style.border = me.Border(
            bottom=me.BorderSide(width=2, style="solid", color=me.theme_var("primary")),
        )
        style.cursor = "default"
    return style


def _make_default_tab_style():
    """Basic styles shared by different tab state (selected, disabled, default)."""
    return me.Style(
        align_items="center",
        color=me.theme_var("on-surface-variant"),
        display="flex",
        cursor="pointer",
        flex_grow=1,
        justify_content="center",
        line_height=1,
        font_size=14,
        font_weight="medium",
        padding=me.Padding(top=12, bottom=12, left=16, right=16),
        text_align="center",
        gap=8,
    )


@me.component
def description_tabs(
    image_descriptions: list[str],
    critique_questions: list[str],
):
    """A component for displaying descriptions and questions in a tabbed view."""
    state = me.state(State)

    # Create tabs for image descriptions
    tabs = []
    for i, description in enumerate(image_descriptions):
        tabs.append(
            Tab(
                label=f"Image {i + 1}",
                icon="image",
                content=lambda desc=description: _description_tab_content(desc),
            ),
        )

    # Create tab for critique questions if they exist
    if critique_questions:
        tabs.append(
            Tab(
                label="Critique Questions",
                icon="quiz",
                content=lambda: _questions_tab_content(critique_questions),
            ),
        )

    if not tabs:
        return

    # Adjust selected index if it's out of bounds
    if state.selected_tab_index >= len(tabs):
        state.selected_tab_index = len(tabs) - 1

    for index, tab in enumerate(tabs):
        tab.selected = state.selected_tab_index == index

    _tab_header(tabs, on_tab_click)
    _tab_content(tabs)
