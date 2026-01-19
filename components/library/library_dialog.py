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

from collections.abc import Callable

import mesop as me

from common.metadata import MediaItem
from components.dialog import dialog
from components.library.events import LibrarySelectionChangeEvent
from components.library.library_image_selector import library_image_selector


@me.component
def library_dialog(
    is_open: bool,
    on_select: Callable[[LibrarySelectionChangeEvent], None],
    on_close: Callable[[me.ClickEvent], None],
    media_items: list[MediaItem],
    is_loading: bool,
):
    """A dialog that displays the media library for image selection.
    This component is fully controlled by a parent page.
    """
    dialog_style = me.Style(
        width="65vw",
        height="35vh",
        display="flex",
        flex_direction="column",
    )

    with dialog(is_open=is_open, dialog_style=dialog_style), me.box(
        style=me.Style(display="flex", flex_direction="column", gap=16, flex_grow=1),
    ):
        me.text("Select an Image from Library", type="headline-6")
        with me.box(style=me.Style(flex_grow=1, overflow_y="auto")):
            if is_loading:
                with me.box(
                    style=me.Style(
                        display="flex",
                        justify_content="center",
                        align_items="center",
                        height="100%",
                    ),
                ):
                    me.progress_spinner()
            else:
                library_image_selector(
                    on_select=on_select,
                    media_items=media_items,
                )
        with me.box(
            style=me.Style(
                display="flex", justify_content="flex-end", margin=me.Margin(top=24),
            ),
        ):
            me.button(
                "Cancel",
                on_click=on_close,
                type="stroked",
            )
