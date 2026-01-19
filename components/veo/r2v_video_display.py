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
from state.veo_and_me_state import PageState  # Correct state import

from common.utils import gcs_uri_to_https_url

from ..video_thumbnail.video_thumbnail import video_thumbnail


@me.component
def r2v_video_display(on_thumbnail_click: Callable):
    """Display the generated video(s) for the R2V page."""
    state = me.state(PageState)

    with me.box(
        style=me.Style(
            display="flex",
            flex_direction="column",
            align_items="center",
            width="100%",
        ),
    ):
        if state.is_loading:
            with me.box(
                style=me.Style(
                    display="flex", justify_content="center", margin=me.Margin(top=24),
                ),
            ):
                me.progress_spinner()
            me.text(
                state.timing if state.timing else "Generating video...",
                style=me.Style(margin=me.Margin(top=16)),
            )
            return

        if not state.result_videos:
            me.text(
                "Your generated videos will appear here.",
                style=me.Style(
                    padding=me.Padding.all(24), color=me.theme_var("on-surface-variant"),
                ),
            )
            return

        # Determine the main video to display
        main_video_url = (
            state.selected_video_url
            if state.selected_video_url
            else state.result_videos[0]
        )

        # Main video player
        me.video(
            key=main_video_url,  # Add key to force re-render
            src=gcs_uri_to_https_url(main_video_url),
            style=me.Style(
                border_radius=12,
                width="100%",
                max_width="90vh",
                display="block",
                margin=me.Margin(left="auto", right="auto"),
            ),
        )

        # Generation time
        with me.box(
            style=me.Style(
                display="flex",
                flex_direction="row",
                gap=15,
                align_items="center",
                justify_content="center",
                padding=me.Padding(top=10),
            ),
        ):
            me.text(state.timing)

        # Thumbnail strip for multiple videos
        if len(state.result_videos) > 1:
            with me.box(
                style=me.Style(
                    display="flex",
                    flex_direction="row",
                    gap=16,
                    justify_content="center",
                    margin=me.Margin(top=16),
                    flex_wrap="wrap",
                ),
            ):
                for url in state.result_videos:
                    is_selected = url == main_video_url
                    with me.box(style=me.Style(height="90px", width="160px")):
                        video_thumbnail(
                            key=url,
                            video_src=gcs_uri_to_https_url(url),
                            selected=is_selected,
                            on_click=on_thumbnail_click,
                        )
