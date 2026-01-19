"""An accordion component for displaying descriptions and questions."""

from collections.abc import Callable

import mesop as me


@me.component
def description_accordion(
    image_descriptions: list[str],
    critique_questions: list[str],
    expanded_panels: dict[str, bool],
    on_toggle: Callable,
):
    """A component for displaying descriptions and questions in an accordion view."""
    with me.accordion():
        # Create expansion panels for image descriptions
        for i, description in enumerate(image_descriptions):
            panel_key = f"image_{i}"
            with me.expansion_panel(
                key=panel_key,
                title=f"Image {i + 1} Description",
                icon="image",
                expanded=expanded_panels.get(panel_key, False),
                on_toggle=on_toggle,
            ):
                me.textarea(
                    value=description,
                    readonly=True,
                    rows=4,
                    autosize=True,
                    style=me.Style(
                        width="100%",
                        font_size="12pt",
                        border=None,
                        background="transparent",
                    ),
                )

        # Create expansion panel for critique questions
        if critique_questions:
            panel_key = "questions"
            with me.expansion_panel(
                key=panel_key,
                title="Critique Questions",
                icon="quiz",
                expanded=expanded_panels.get(panel_key, False),
                on_toggle=on_toggle,
            ), me.box(
                style=me.Style(display="flex", flex_direction="column", gap=8),
            ):
                for i, question in enumerate(critique_questions):
                    me.text(f"{i + 1}. {question}")
