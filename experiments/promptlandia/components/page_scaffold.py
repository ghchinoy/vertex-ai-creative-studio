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
import mesop as me

from components.side_nav import sidenav
from components.styles import (
    MAIN_COLUMN_STYLE,
    PAGE_BACKGROUND_PADDING_STYLE,
    PAGE_BACKGROUND_STYLE,
    SIDENAV_MAX_WIDTH,
    SIDENAV_MIN_WIDTH,
)
from state.state import AppState


@me.content_component
def page_scaffold():
    """Provides the main page scaffold for the application.

    This component creates the basic layout for all pages, including the side
    navigation bar and the main content area. It uses the `sidenav` component
    and provides a slot for the page-specific content.
    """
    app_state = me.state(AppState)

    sidenav("")

    with (
        me.box(
            style=me.Style(
                display="flex",
                flex_direction="column",
                height="100%",
                margin=me.Margin(
                    left=SIDENAV_MAX_WIDTH
                    if app_state.sidenav_open
                    else SIDENAV_MIN_WIDTH,
                ),
            ),
        ),
        me.box(
            style=me.Style(
                background=me.theme_var("background"),
                height="100%",
                overflow_y="scroll",
                margin=me.Margin(bottom=20),
            ),
        ),
    ):
        me.slot()


@me.content_component
def page_frame():
    """Provides a frame for the main content of a page.

    This component creates a styled container for the main content of a page,
    ensuring a consistent look and feel across the application.
    """
    with me.box(style=MAIN_COLUMN_STYLE), me.box(style=PAGE_BACKGROUND_STYLE):
        with me.box(style=PAGE_BACKGROUND_PADDING_STYLE):
            me.slot()
