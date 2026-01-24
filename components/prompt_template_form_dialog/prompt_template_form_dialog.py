# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Dialog for viewing and editing a PromptTemplate."""

from collections.abc import Callable
from typing import Literal

import mesop as me

from common.utils import create_display_url
from components.dialog import dialog


@me.stateclass
class DialogState:
    """State for the detail dialog."""

    # To hold the edited values
    label: str = ""
    key: str = ""
    category: str = ""
    prompt: str = ""
    template_type: str = ""


@me.component
def prompt_template_form_dialog(
    template: dict | None,
    mode: Literal["view", "edit", "create"],
    is_open: bool,
    on_close: Callable,
    on_update: Callable | None = None,  # For edits
    on_save: Callable | None = None,  # For creates
):
    """A unified dialog for viewing, editing, and creating a prompt template."""
    state = me.state(DialogState)

    # Determine if the form is for editing/creating vs. just viewing
    is_editable = mode in ["edit", "create"]

    # Determine the dialog title based on the mode
    title = "View Template"
    if mode == "edit":
        title = f"Edit Template: {template.get('label', '')}"
    elif mode == "create":
        title = "Save as Prompt Template"

    # State synchronization logic for edit mode
    if is_open and mode == "edit" and template and state.key != template.get("key"):
        state.label = template.get("label", "")
        state.key = template.get("key", "")
        state.category = template.get("category", "")
        state.prompt = template.get("prompt", "")
        state.template_type = template.get("template_type", "text")

    # For create mode, the prompt can be passed in via the `template` dict
    if is_open and mode == "create" and template and not state.prompt:
        state.prompt = template.get("prompt", "")

    def handle_save(e: me.ClickEvent):
        if mode == "edit":
            yield from on_update(
                template["id"],
                {
                    "label": state.label,
                    "key": state.key,
                    "category": state.category,
                    "prompt": state.prompt,
                    "template_type": state.template_type,
                },
            )
        elif mode == "create":
            # For create, we pass the individual fields to the handler
            yield from on_save(state.label, state.key, state.category, state.prompt)

        # Clear state after action
        state.label = ""
        state.key = ""
        state.category = ""
        state.prompt = ""
        state.template_type = ""

    def handle_close(e: me.ClickEvent):
        # Clear state before closing
        state.label = ""
        state.key = ""
        state.category = ""
        state.prompt = ""
        state.template_type = ""
        # Call the parent's on_close handler
        yield from on_close(e)

    with dialog(is_open=is_open):  # pylint: disable=E1129:not-context-manager
        # We need content to render if we are creating, or if we have a template for viewing/editing
        if mode == "create" or template:
            with me.box(
                style=me.Style(
                    padding=me.Padding.all(24),
                    display="flex",
                    flex_direction="column",
                    gap=16,
                ),
            ):
                me.text(title, type="headline-5")

                # Display fields
                if is_editable:
                    # Create mode specific behavior could go here if needed
                    if mode == "create":
                        me.text("Prompt to save:")
                        me.text(
                            state.prompt,
                            style=me.Style(
                                font_style="italic",
                                max_height="150px",
                                overflow_y="auto",
                            ),
                        )

                    me.input(
                        label="Label",
                        value=state.label,
                        on_blur=lambda e: setattr(state, "label", e.value),
                    )
                    me.input(
                        label="Key",
                        value=state.key,
                        on_blur=lambda e: setattr(state, "key", e.value),
                    )
                    me.input(
                        label="Category",
                        value=state.category,
                        on_blur=lambda e: setattr(state, "category", e.value),
                    )
                    # Only show type and prompt for edit, not create
                    if mode == "edit":
                        me.input(
                            label="Type",
                            value=state.template_type,
                            on_blur=lambda e: setattr(state, "template_type", e.value),
                        )
                        me.textarea(
                            label="Prompt",
                            value=state.prompt,
                            on_blur=lambda e: setattr(state, "prompt", e.value),
                            rows=5,
                            autosize=True,
                            style=me.Style(width="100%"),
                        )

                else:  # View mode
                    _detail_row("Key:", template["key"])
                    _detail_row("Category:", template["category"])
                    _detail_row("Type:", template["template_type"])
                    _detail_row("Attribution:", template["attribution"])
                    if template.get("created_at"):
                        _detail_row("Created:", str(template["created_at"]))
                    if template.get("updated_at"):
                        _detail_row("Last Edited:", str(template["updated_at"]))
                    me.text(
                        "Prompt:",
                        style=me.Style(font_weight="bold", margin=me.Margin(top=16)),
                    )
                    with me.box(
                        style=me.Style(
                            background=me.theme_var("surface-container"),
                            padding=me.Padding.all(16),
                            border_radius=8,
                            max_height="300px",
                            overflow_y="auto",
                        ),
                    ):
                        me.text(template["prompt"])

            # Display references if they exist
            if template and template.get("references"):
                me.text(
                    "References:",
                    style=me.Style(font_weight="bold", margin=me.Margin(top=16)),
                )
                with me.box(
                    style=me.Style(
                        display="flex",
                        flex_direction="row",
                        gap=8,
                        flex_wrap="wrap",
                    ),
                ):
                    for ref_uri in template["references"]:
                        me.image(
                            src=create_display_url(ref_uri),
                            style=me.Style(
                                width=100,
                                height=100,
                                border_radius=8,
                                object_fit="cover",
                            ),
                        )

            with me.box(
                style=me.Style(
                    display="flex",
                    justify_content="flex-end",
                    gap=8,
                    margin=me.Margin(top=24),
                ),
            ):
                me.button("Close", on_click=handle_close, type="stroked")
                if is_editable:
                    me.button("Save", on_click=handle_save, type="raised")


@me.component
def _detail_row(label: str, value: str):
    with me.box(style=me.Style(display="flex", flex_direction="row", gap=8)):
        me.text(label, style=me.Style(font_weight="bold"))
        me.text(value)
