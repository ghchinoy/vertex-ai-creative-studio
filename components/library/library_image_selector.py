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
from components.library.events import LibrarySelectionChangeEvent
from components.media_tile.media_tile import get_pills_for_item, media_tile


@me.component
def library_image_selector(
    on_select: Callable[[LibrarySelectionChangeEvent], None],
    media_items: list[MediaItem],
):
    """A component that displays a grid of recent media items from the library."""

    def on_media_click(e: me.WebEvent):
        """Handles the click event on a media tile."""
        print(f"Media Clicked. URI from key: {e.key}")
        yield from on_select(LibrarySelectionChangeEvent(gcs_uri=e.key))

    with me.box(
        style=me.Style(
            display="grid",
            grid_template_columns="repeat(auto-fill, minmax(150px, 1fr))",
            gap="16px",
        ),
    ):
        if not media_items:
            me.text("No recent items found in the library.")
        else:
            for item in media_items:
                # The signed_url attribute is now added by the parent component.
                https_url = item.signed_url if hasattr(item, "signed_url") else ""
                gcs_uri = item.gcsuri or (item.gcs_uris[0] if item.gcs_uris else None)

                # Explicitly determine render type for the tile if possible
                render_type = item.media_type
                if not render_type and item.mime_type:
                    if item.mime_type.startswith("video/"):
                        render_type = "video"
                    elif item.mime_type.startswith("audio/"):
                        render_type = "audio"
                    elif item.mime_type.startswith("image/"):
                        render_type = "image"

                if gcs_uri:
                    media_tile(
                        key=gcs_uri,
                        on_click=on_media_click,
                        media_type=render_type,
                        https_url=https_url,
                        pills_json=get_pills_for_item(item, https_url),
                    )
