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
"""Component for displaying video details."""

import os
from collections.abc import Callable
from datetime import datetime

import mesop as me

from common.metadata import MediaItem
from common.utils import create_display_url
from components.download_button.download_button import download_button
from components.media_tile.media_tile import media_tile


@me.component
def video_details(
    item: MediaItem,
    on_click_permalink: Callable,
    selected_url: str,
    on_thumbnail_click: Callable,
):
    """Renders the details for a video item, including a gallery for multiple videos."""
    with me.box(
        style=me.Style(
            display="flex",
            flex_direction="column",
            gap=12,
        ),
    ):
        # Main video player
        if selected_url and not item.error_message:
            with me.box(
                style=me.Style(width="100%", height=400, margin=me.Margin(bottom=16))
            ):
                media_tile(
                    key=selected_url,
                    media_type="video",
                    https_url=create_display_url(selected_url),
                    controls=True,
                    object_fit="contain",
                )

        # Thumbnail strip for multiple videos
        if item.gcs_uris and len(item.gcs_uris) > 1:
            with me.box(
                style=me.Style(
                    display="flex",
                    flex_direction="row",
                    gap=16,
                    justify_content="center",
                    margin=me.Margin(top=16, bottom=16),
                    flex_wrap="wrap",
                ),
            ):
                for url in item.gcs_uris:
                    is_selected = url == selected_url
                    with me.box(style=me.Style(height="90px", width="160px")):
                        media_tile(
                            key=url,
                            media_type="video",
                            https_url=create_display_url(url),
                            selected=is_selected,
                            on_click=on_thumbnail_click,
                        )

        if item.error_message:
            me.text(
                f"Error: {item.error_message}",
                style=me.Style(
                    color=me.theme_var("error"),
                    font_style="italic",
                    padding=me.Padding.all(8),
                    background=me.theme_var("error-container"),
                    border_radius=4,
                    margin=me.Margin(bottom=10),
                ),
            )

        me.text(f"Model: {item.raw_data['model']}")
        me.text(f'Prompt: "{item.prompt or "N/A"}"')
        if item.negative_prompt:
            me.text(f'Negative Prompt: "{item.negative_prompt}"')
        if item.enhanced_prompt_used:
            me.text(f'Enhanced Prompt: "{item.enhanced_prompt_used}"')

        dialog_timestamp_str_detail = "N/A"
        if item.timestamp:
            try:
                ts_str_detail = item.timestamp
                if isinstance(item.timestamp, datetime):
                    ts_str_detail = item.timestamp.isoformat()
                dialog_timestamp_str_detail = datetime.fromisoformat(
                    ts_str_detail.replace("Z", "+00:00"),
                ).strftime("%Y-%m-%d %H:%M:%S %Z")
            except Exception:
                dialog_timestamp_str_detail = str(item.timestamp)
        me.text(f"Generated: {dialog_timestamp_str_detail}")

        if item.generation_time is not None:
            me.text(f"Generation Time: {round(item.generation_time, 2)} seconds")

        if item.model is not None:
            me.text(f"Model: {item.model}")

        if item.aspect:
            me.text(f"Aspect Ratio: {item.aspect}")
        if item.duration is not None:
            me.text(f"Duration: {item.duration} seconds")
        me.text(f"Resolution: {item.resolution or '720p'}")

        if item.reference_image:
            ref_url = create_display_url(item.reference_image)
            me.text(
                "Reference Image:",
                style=me.Style(
                    font_weight="500",
                    margin=me.Margin(top=8),
                ),
            )
            with me.box(style=me.Style(width=250, height=250, margin=me.Margin(top=4))):
                media_tile(
                    media_type="image",
                    https_url=ref_url,
                    object_fit="contain",
                )
        if item.last_reference_image:
            last_ref_url = create_display_url(item.last_reference_image)
            me.text(
                "Last Reference Image:",
                style=me.Style(font_weight="500", margin=me.Margin(top=8)),
            )
            with me.box(style=me.Style(width=250, height=250, margin=me.Margin(top=4))):
                media_tile(
                    media_type="image",
                    https_url=last_ref_url,
                    object_fit="contain",
                )

        with me.box(
            style=me.Style(
                display="flex",
                flex_direction="row",
                gap=10,
                margin=me.Margin(top=16),
            ),
        ):
            with me.content_button(
                on_click=on_click_permalink,
                key=item.id or "",  # Ensure key is not None
            ):
                with me.box(
                    style=me.Style(
                        display="flex",
                        flex_direction="row",
                        align_items="center",
                        gap=5,
                    ),
                ):
                    me.icon(icon="link")
                    me.text("permalink")

            # Download button should download the selected video
            if selected_url:
                filename = os.path.basename(selected_url.split("?")[0])
                download_button(url=selected_url, filename=filename)
