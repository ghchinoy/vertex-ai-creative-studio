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
"""Component for displaying a video item in the library grid."""

import mesop as me

from common.metadata import MediaItem
from common.utils import create_display_url
from components.media_tile.media_tile import media_tile
from components.pill import pill


@me.component
def video_grid_item(item: MediaItem):
    """Renders a grid item for a video media type."""
    item_duration_str = (
        f"{item.duration} sec" if item.duration is not None else "N/A"
    )
    gcs_uri = (
        item.gcsuri
        if item.gcsuri
        else (item.gcs_uris[0] if item.gcs_uris else None)
    )
    item_url = create_display_url(gcs_uri)

    # The user reported the pill was not showing. This debug line was added to investigate.
    # It can be removed once the issue is confirmed fixed.
    print(
        f"DEBUG: Grid item {item.id}, gcs_uris: {item.gcs_uris}, length: {len(item.gcs_uris) if item.gcs_uris else 0}",
    )
    with me.box(
        style=me.Style(
            display="flex",
            flex_wrap="wrap",
            gap=5,
            margin=me.Margin(bottom=8),
        ),
    ):
        pill("Video", "media_type_video")
        if item.gcs_uris and len(item.gcs_uris) > 1:
            pill(f"{len(item.gcs_uris)}", "multi_video")
        pill(
            "t2v" if not item.reference_image else "i2v",
            "gen_t2v" if not item.reference_image else "gen_i2v",
        )
        if item.aspect:
            pill(item.aspect, "aspect")
        if item.duration is not None:
            pill(item_duration_str, "duration")
        if item.resolution:
            pill(item.resolution, "resolution")
        pill("24 fps", "fps")
        if item.enhanced_prompt_used:
            with me.tooltip(message="Prompt was auto-enhanced"):
                me.icon(
                    "auto_fix_normal",
                    style=me.Style(color=me.theme_var("primary")),
                )

    # Media Preview Section
    with me.box(
        style=me.Style(
            display="flex",
            flex_direction="row",
            gap=8,
            align_items="center",
            justify_content="center",
            margin=me.Margin(top=8, bottom=8),
            min_height="100px",  # Adjusted height
        ),
    ):
        if item_url:
            # Use the new, robust media_tile component
            with me.box(style=me.Style(width=160, height=90)):
                media_tile(
                    media_type="video",
                    https_url=item_url,
                )
        else:
            me.text(
                "Video not available.",
                style=me.Style(
                    height="100px",  # Adjusted height
                    display="flex",
                    align_items="center",
                    justify_content="center",
                    color=me.theme_var("onsurfacevariant"),
                ),
            )

        # Reference images for video
        with me.box(
            style=me.Style(
                display="flex",
                flex_direction="column",
                gap=5,
            ),
        ):
            if item.reference_image:
                ref_img_url = create_display_url(item.reference_image)
                with me.box(style=me.Style(width=70, height=70)):
                    media_tile(
                        media_type="image",
                        https_url=ref_img_url,
                        object_fit="contain",
                    )
            if item.last_reference_image:
                last_ref_img_url = create_display_url(item.last_reference_image)
                with me.box(style=me.Style(width=70, height=70)):
                    media_tile(
                        media_type="image",
                        https_url=last_ref_img_url,
                        object_fit="contain",
                    )
