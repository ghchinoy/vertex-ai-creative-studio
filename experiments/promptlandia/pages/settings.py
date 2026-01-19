# Copyright 2024 Google LLC
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

"""This module defines the settings page of the application.

It displays the underlying prompts that the application itself uses for the
improvement and evaluation tasks, providing transparency into its own workings.
"""

import html

import mesop as me
from models.prompts import (
    PROMPT_HEALTH_CHECKLIST,
    PROMPT_IMPROVEMENT_INSTRUCTIONS,
    PROMPT_IMPROVEMENT_PLANNING_INSTRUCTIONS,
    VIDEO_PROMPT_HEALTH_CHECKLIST,
)

from components.header import header


@me.stateclass
class PageState:
    """Local page state for the settings page."""


def settings_page_content(app_state: me.state):
    """Renders the main content of the settings page.

    Args:
        app_state: The global application state.

    """
    with me.box(
        style=me.Style(
            display="flex",
            flex_direction="column",
            height="100%",
        ),
    ), me.box(
        style=me.Style(
            background=me.theme_var("background"),
            height="100%",
            overflow_y="scroll",
            margin=me.Margin(bottom=20),
        ),
    ), me.box(
        style=me.Style(
            background=me.theme_var("background"),
            padding=me.Padding(top=24, left=24, right=24, bottom=24),
            display="flex",
            flex_direction="column",
        ),
    ):
        header("Settings", "settings")

        me.text("Settings for Promptlandia")
        me.box(style=me.Style(height=32))

        with me.box():
            me.text(
                "Prompt Improvement Instructions",
                style=me.Style(font_weight="bold"),
            )
            me.box(style=me.Style(height=8))
            with me.box(style=PROMPT_BOX_STYLE):
                me.markdown(text=html.escape(PROMPT_IMPROVEMENT_INSTRUCTIONS))

        me.box(style=me.Style(height=32))

        with me.box():
            me.text(
                "Prompt Planning Instructions",
                style=me.Style(font_weight="bold"),
            )
            me.box(style=me.Style(height=8))
            with me.box(style=PROMPT_BOX_STYLE):
                me.markdown(
                    text=html.escape(PROMPT_IMPROVEMENT_PLANNING_INSTRUCTIONS),
                )

        me.box(style=me.Style(height=32))

        with me.box():
            me.text(
                "Prompt Health Checklist",
                style=me.Style(font_weight="bold"),
            )
            me.box(style=me.Style(height=8))
            with me.box(style=PROMPT_BOX_STYLE):
                me.markdown(text=html.escape(PROMPT_HEALTH_CHECKLIST))

        me.box(style=me.Style(height=32))

        with me.box():
            me.text(
                "Video Prompt Health Checklist",
                style=me.Style(font_weight="bold"),
            )
            me.box(style=me.Style(height=8))
            with me.box(style=PROMPT_BOX_STYLE):
                me.markdown(text=html.escape(VIDEO_PROMPT_HEALTH_CHECKLIST))


PROMPT_BOX_STYLE = me.Style(
    display="grid",
    flex_direction="row",
    gap=5,
    align_items="center",
    width="100%",
    background=me.theme_var("on-secondary"),
    border_radius=16,
    padding=me.Padding.all(8),
)
