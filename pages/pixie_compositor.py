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

"""A test page for concatenating videos using moviepy."""

import datetime
from collections.abc import Callable
from dataclasses import dataclass, field

import mesop as me

from common.metadata import (
    MediaItem,
    add_media_item_to_firestore,
)
from common.storage import store_to_gcs
from common.utils import create_display_url
from components.header import header
from components.library.events import LibrarySelectionChangeEvent
from components.library.library_chooser_button import library_chooser_button
from components.page_scaffold import page_frame, page_scaffold
from components.snackbar import snackbar
from models.video_processing import (
    convert_mp4_to_gif,
    layer_audio_on_video,
    process_videos,
)
from state.state import AppState


@me.stateclass
class PageState:
    # Using a dict to store selected videos, keyed by chooser id (e.g., "video_1")
    selected_videos: dict[str, str] = field(default_factory=dict)  # pylint: disable=E3701:invalid-field-call
    selected_videos_display_urls: dict[str, str] = field(default_factory=dict)  # pylint: disable=E3701:invalid-field-call
    concatenated_video_url: str = ""
    concatenated_video_display_url: str = ""
    gif_url: str = ""
    gif_display_url: str = ""
    is_loading: bool = False
    is_converting_gif: bool = False
    error_message: str = ""
    selected_transition: str = "concat"
    show_snackbar: bool = False
    snackbar_message: str = ""
    show_error_dialog: bool = False
    dialog_title: str = ""
    dialog_message: str = ""
    active_tab: str = "video_video"
    selected_video_for_audio: str = ""
    selected_video_for_audio_display_url: str = ""
    selected_audio: str = ""
    selected_audio_display_url: str = ""


VIDEO_PLACEHOLDER_STYLE = me.Style(
    width=360,
    height=200,
    border=me.Border.all(
        me.BorderSide(width=2, style="dashed", color=me.theme_var("outline-variant")),
    ),
    border_radius=8,
    display="flex",
    align_items="center",
    justify_content="center",
    flex_direction="column",
    gap=8,
)


@me.page(
    path="/pixie_compositor",
    title="Pixie Compositor",
)
def pixie_compositor_page():
    with page_scaffold(page_name="pixie_compositor"):  # pylint: disable=E1129:not-context-manager
        with page_frame():  # pylint: disable=E1129:not-context-manager
            header("Pixie Compositor", "auto_fix_high")
            page_content()


# Adapted from components/tab_nav.py
@dataclass
class Tab:
    key: str
    label: str
    icon: str | None = None


def on_tab_change(e: me.ClickEvent):
    state = me.state(PageState)
    state.active_tab = e.key
    yield


@me.component
def _tab_group(tabs: list[Tab], on_tab_click: Callable, selected_tab_key: str):
    with me.box(
        style=me.Style(
            display="flex",
            border=me.Border(
                bottom=me.BorderSide(
                    width=1, style="solid", color=me.theme_var("outline-variant"),
                ),
            ),
        ),
    ):
        for tab in tabs:
            is_selected = tab.key == selected_tab_key
            with me.box(
                key=tab.key,
                on_click=on_tab_click,
                style=_make_tab_style(is_selected),
            ):
                if tab.icon:
                    me.icon(tab.icon)
                me.text(tab.label)


def _make_tab_style(selected: bool) -> me.Style:
    style = me.Style(
        align_items="center",
        color=me.theme_var("on-surface"),
        display="flex",
        cursor="pointer",
        flex_grow=1,
        justify_content="center",
        line_height=1,
        font_size=14,
        font_weight="medium",
        padding=me.Padding.all(16),
        text_align="center",
        gap=5,
    )
    if selected:
        style.background = me.theme_var("surface-container")
        style.border = me.Border(
            bottom=me.BorderSide(width=2, style="solid", color=me.theme_var("primary")),
        )
        style.cursor = "default"
    return style


def page_content():
    state = me.state(PageState)

    tabs = [
        Tab(key="video_video", label="Video + Video", icon="movie"),
        Tab(key="video_audio", label="Video + Audio", icon="music_video"),
    ]

    _tab_group(tabs=tabs, on_tab_click=on_tab_change, selected_tab_key=state.active_tab)

    # Conditionally render tab content
    if state.active_tab == "video_video":
        render_video_video_tab()
    elif state.active_tab == "video_audio":
        render_video_audio_tab()

    snackbar(is_visible=state.show_snackbar, label=state.snackbar_message)


def render_video_video_tab():
    state = me.state(PageState)
    with me.box(
        style=me.Style(
            display="flex", flex_direction="column", gap=20, margin=me.Margin(top=20),
        ),
    ):
        me.text("Select two videos from the library to process.")

        # Video Selection Area
        with me.box(
            style=me.Style(
                display="flex", flex_direction="row", gap=20, justify_content="center",
            ),
        ):
            # Video 1 Selector
            with me.box(
                style=me.Style(display="flex", flex_direction="column", gap=10),
            ):
                me.text("Video 1")
                with me.box(
                    style=me.Style(
                        display="flex",
                        flex_direction="row",
                        gap=8,
                        align_items="center",
                    ),
                ):
                    me.uploader(
                        label="Upload Video",
                        on_upload=on_upload_video_1,
                        accepted_file_types=["video/mp4", "video/quicktime"],
                        style=me.Style(width="100%"),
                    )
                    library_chooser_button(
                        key="video_1",
                        on_library_select=on_video_select,
                        media_type=["videos"],
                    )
                with me.box(style=VIDEO_PLACEHOLDER_STYLE):
                    if "video_1" in state.selected_videos_display_urls:
                        me.video(
                            key=state.selected_videos[
                                "video_1"
                            ],  # Add key to force re-render
                            src=state.selected_videos_display_urls["video_1"],
                            style=me.Style(
                                height="100%",
                                width="100%",
                                border_radius=8,
                                object_fit="contain",
                            ),
                        )
                    else:
                        me.icon("movie")
                        me.text("Select Video 1")

            # Video 2 Selector
            with me.box(
                style=me.Style(display="flex", flex_direction="column", gap=10),
            ):
                me.text("Video 2")
                with me.box(
                    style=me.Style(
                        display="flex",
                        flex_direction="row",
                        gap=8,
                        align_items="center",
                    ),
                ):
                    me.uploader(
                        label="Upload Video",
                        on_upload=on_upload_video_2,
                        accepted_file_types=["video/mp4", "video/quicktime"],
                        style=me.Style(width="100%"),
                    )
                    library_chooser_button(
                        key="video_2",
                        on_library_select=on_video_select,
                        media_type=["videos"],
                    )
                with me.box(style=VIDEO_PLACEHOLDER_STYLE):
                    if "video_2" in state.selected_videos_display_urls:
                        me.video(
                            key=state.selected_videos[
                                "video_2"
                            ],  # Add key to force re-render
                            src=state.selected_videos_display_urls["video_2"],
                            style=me.Style(
                                height="100%", width="100%", border_radius=8,
                            ),
                        )
                    else:
                        me.icon("movie")
                        me.text("Select Video 2")

        # Controls
        with me.box(
            style=me.Style(
                display="flex",
                gap=16,
                flex_direction="row",
                align_items="center",
                justify_content="center",
            ),
        ):
            # Transition Selector
            me.select(
                label="Transition",
                options=[
                    me.SelectOption(label="Concatenate", value="concat"),
                    me.SelectOption(label="Crossfade", value="x-fade"),
                    me.SelectOption(label="Wipe", value="wipe"),
                    me.SelectOption(label="Dip to Black", value="dipToBlack"),
                ],
                value=state.selected_transition,
                on_selection_change=on_transition_change,
            )

            # Process Button
            me.button(
                "Process Videos",
                on_click=on_process_click,
                disabled=len(state.selected_videos) < 2 or state.is_loading,
                type="raised",
            )

        # Result Area
        if state.is_loading:
            with me.box(style=me.Style(display="flex", justify_content="center")):
                me.progress_spinner()

        if state.error_message:
            me.text(state.error_message, style=me.Style(color="red"))

        # result video
        if state.concatenated_video_display_url:
            with me.box(
                style=me.Style(
                    display="flex",
                    flex_direction="column",
                    align_items="center",
                    gap=10,
                ),
            ):
                me.video(
                    src=state.concatenated_video_display_url,
                    style=me.Style(width="100%", max_width="720px", border_radius=8),
                )
                me.button(
                    "Convert to GIF",
                    on_click=on_convert_to_gif_click,
                    disabled=state.is_converting_gif,
                )

        if state.is_converting_gif:
            with me.box(style=me.Style(display="flex", justify_content="center")):
                me.progress_spinner()

        if state.gif_display_url:
            with me.box(
                style=me.Style(
                    display="flex",
                    flex_direction="column",
                    align_items="center",
                    gap=10,
                ),
            ):
                me.text("Video as GIF:", type="headline-5")
                me.image(
                    src=state.gif_display_url,
                    style=me.Style(width="100%", max_width="480px", border_radius=8),
                )


def render_video_audio_tab():
    state = me.state(PageState)
    with me.box(
        style=me.Style(
            display="flex", flex_direction="column", gap=20, margin=me.Margin(top=20),
        ),
    ):
        me.text("Select a video and an audio file to layer.")

        # Media Selection Area
        with me.box(
            style=me.Style(
                display="flex", flex_direction="row", gap=20, justify_content="center",
            ),
        ):
            # Video Selector
            with me.box(
                style=me.Style(display="flex", flex_direction="column", gap=10),
            ):
                me.text("Video")
                with me.box(
                    style=me.Style(
                        display="flex",
                        flex_direction="row",
                        gap=8,
                        align_items="center",
                    ),
                ):
                    me.uploader(
                        label="Upload Video",
                        on_upload=on_upload_video_for_audio,
                        accepted_file_types=["video/mp4", "video/quicktime"],
                        style=me.Style(width="100%"),
                    )
                    library_chooser_button(
                        key="video_for_audio",
                        on_library_select=on_video_select_for_audio,
                        media_type=["videos"],
                    )
                with me.box(style=VIDEO_PLACEHOLDER_STYLE):
                    if state.selected_video_for_audio_display_url:
                        me.video(
                            key=state.selected_video_for_audio,  # Add key to force re-render
                            src=state.selected_video_for_audio_display_url,
                            style=me.Style(
                                height="100%",
                                width="100%",
                                border_radius=8,
                                object_fit="contain",
                            ),
                        )
                    else:
                        me.icon("movie")
                        me.text("Select a Video")

            # Audio Selector
            with me.box(
                style=me.Style(display="flex", flex_direction="column", gap=10),
            ):
                me.text("Audio")
                with me.box(
                    style=me.Style(
                        display="flex",
                        flex_direction="row",
                        gap=8,
                        align_items="center",
                    ),
                ):
                    me.uploader(
                        label="Upload Audio",
                        on_upload=on_upload_audio,
                        accepted_file_types=["audio/mpeg", "audio/wav"],
                        style=me.Style(width="100%"),
                    )
                    library_chooser_button(
                        key="audio_1",
                        on_library_select=on_audio_select_from_library,
                        media_type=["audio"],
                    )
                    # Future: Add audio_chooser_button if created
                with me.box(style=VIDEO_PLACEHOLDER_STYLE):
                    if state.selected_audio_display_url:
                        me.audio(
                            src=state.selected_audio_display_url,
                        )
                    else:
                        me.icon("music_note")
                        me.text("Select an Audio File")

        # Controls
        with me.box(
            style=me.Style(
                display="flex",
                gap=16,
                flex_direction="row",
                align_items="center",
                justify_content="center",
            ),
        ):
            me.button(
                "Layer Audio on Video",
                on_click=on_layer_audio_click,
                disabled=not state.selected_video_for_audio
                or not state.selected_audio
                or state.is_loading,
                type="raised",
            )

        # Result Area (reusing components from the other tab)
        if state.is_loading:
            with me.box(style=me.Style(display="flex", justify_content="center")):
                me.progress_spinner()

        if state.error_message:
            me.text(state.error_message, style=me.Style(color="red"))

        if state.concatenated_video_display_url:
            with me.box(
                style=me.Style(
                    display="flex",
                    flex_direction="column",
                    align_items="center",
                    gap=10,
                ),
            ):
                me.video(
                    src=state.concatenated_video_display_url,
                    style=me.Style(width="100%", max_width="720px", border_radius=8),
                )


def on_upload_video_for_audio(e: me.UploadEvent):
    """Upload video handler for the audio tab."""
    state = me.state(PageState)
    gcs_url = store_to_gcs(
        "pixie_compositor_uploads", e.file.name, e.file.mime_type, e.file.getvalue(),
    )
    state.selected_video_for_audio = gcs_url
    state.selected_video_for_audio_display_url = create_display_url(gcs_url)
    yield


def on_video_select_for_audio(e: LibrarySelectionChangeEvent):
    state = me.state(PageState)
    state.selected_video_for_audio = e.gcs_uri
    state.selected_video_for_audio_display_url = create_display_url(e.gcs_uri)
    yield


def on_upload_audio(e: me.UploadEvent):
    """Upload audio handler for the audio tab."""
    state = me.state(PageState)
    gcs_url = store_to_gcs(
        "pixie_compositor_uploads", e.file.name, e.file.mime_type, e.file.getvalue(),
    )
    state.selected_audio = gcs_url
    state.selected_audio_display_url = create_display_url(gcs_url)
    yield


def on_audio_select_from_library(e: LibrarySelectionChangeEvent):
    state = me.state(PageState)
    state.selected_audio = e.gcs_uri
    state.selected_audio_display_url = create_display_url(e.gcs_uri)
    yield


def on_layer_audio_click(e: me.ClickEvent):
    state = me.state(PageState)
    app_state = me.state(AppState)
    state.is_loading = True
    state.concatenated_video_url = ""
    state.gif_url = ""
    state.error_message = ""
    yield

    try:
        processed_uri = layer_audio_on_video(
            state.selected_video_for_audio, state.selected_audio,
        )
        state.concatenated_video_url = processed_uri
        state.concatenated_video_display_url = create_display_url(processed_uri)

        # Log to Firestore
        add_media_item_to_firestore(
            MediaItem(
                gcsuri=processed_uri,
                user_email=app_state.user_email,
                timestamp=datetime.datetime.now(datetime.UTC),
                mime_type="video/mp4",
                source_uris=[state.selected_video_for_audio, state.selected_audio],
                comment="Produced by Pixie Compositor: Video + Audio",
                model="pixie-compositor-v1-audio-layer",
            ),
        )

    except Exception as ex:
        state.error_message = f"An error occurred: {ex}"
    finally:
        state.is_loading = False
        yield


def show_snackbar(state: PageState, message: str):
    """Displays a snackbar message at the bottom of the page."""
    state.snackbar_message = message
    state.show_snackbar = True
    yield


def on_close_dialog(e: me.ClickEvent):
    state = me.state(PageState)
    state.show_error_dialog = False
    yield


def on_upload_video_1(e: me.UploadEvent):
    """Upload video 1 handler."""
    state = me.state(PageState)
    gcs_url = store_to_gcs(
        "pixie_compositor_uploads", e.file.name, e.file.mime_type, e.file.getvalue(),
    )
    state.selected_videos["video_1"] = gcs_url
    state.selected_videos_display_urls["video_1"] = create_display_url(gcs_url)
    yield


def on_upload_video_2(e: me.UploadEvent):
    """Upload video 2 handler."""
    state = me.state(PageState)
    gcs_url = store_to_gcs(
        "pixie_compositor_uploads", e.file.name, e.file.mime_type, e.file.getvalue(),
    )
    state.selected_videos["video_2"] = gcs_url
    state.selected_videos_display_urls["video_2"] = create_display_url(gcs_url)
    yield


def on_video_select(e: LibrarySelectionChangeEvent):
    state = me.state(PageState)
    # The key of the chooser button tells us which video slot to fill.
    state.selected_videos[e.chooser_id] = e.gcs_uri
    state.selected_videos_display_urls[e.chooser_id] = create_display_url(e.gcs_uri)
    yield


def on_transition_change(e: me.SelectSelectionChangeEvent):
    state = me.state(PageState)
    state.selected_transition = e.value
    yield


def on_process_click(e: me.ClickEvent):
    state = me.state(PageState)
    app_state = me.state(AppState)
    state.is_loading = True
    state.concatenated_video_url = ""
    state.gif_url = ""
    state.error_message = ""
    yield

    try:
        # Ensure videos are in order before processing
        video_uris_to_process = [
            state.selected_videos["video_1"],
            state.selected_videos["video_2"],
        ]
        processed_uri = process_videos(video_uris_to_process, state.selected_transition)
        state.concatenated_video_url = processed_uri
        state.concatenated_video_display_url = create_display_url(processed_uri)

        # Log to Firestore
        add_media_item_to_firestore(
            MediaItem(
                gcsuri=processed_uri,
                user_email=app_state.user_email,
                timestamp=datetime.datetime.now(datetime.UTC),
                mime_type="video/mp4",
                source_uris=video_uris_to_process,
                comment=f"Produced by Pixie Compositor with {state.selected_transition} transition",
                model="pixie-compositor-v1",
            ),
        )
    except ValueError as ex:
        # Catch the specific resolution error and show a dialog
        state.dialog_title = "Resolution Mismatch"
        state.dialog_message = str(ex)
        state.show_error_dialog = True
    except Exception as ex:
        # Catch other generic errors
        state.error_message = f"An error occurred: {ex}"
    finally:
        state.is_loading = False
        yield


def on_convert_to_gif_click(e: me.ClickEvent):
    state = me.state(PageState)
    app_state = me.state(AppState)
    state.is_converting_gif = True
    state.gif_url = ""
    state.gif_display_url = ""
    state.error_message = ""
    yield

    try:
        gif_gcs_uri = convert_mp4_to_gif(
            state.concatenated_video_url, user_email=app_state.user_email,
        )
        state.gif_url = gif_gcs_uri
        state.gif_display_url = create_display_url(gif_gcs_uri)
    except Exception as ex:
        state.error_message = f"An error occurred during GIF conversion: {ex}"
    finally:
        state.is_converting_gif = False
        yield
