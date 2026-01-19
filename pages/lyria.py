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
"""Lyria 2 mesop ui page"""

import datetime  # Required for timestamp
import json
import time
from dataclasses import field

import mesop as me

from common.metadata import MediaItem, add_media_item_to_firestore  # Updated import
from common.utils import create_display_url
from components.dialog import dialog, dialog_actions
from components.header import header
from components.page_scaffold import (
    page_frame,
    page_scaffold,
)
from components.pill import pill
from config.default import Default
from config.rewriters import MUSIC_REWRITER
from models.audio_analysis import analyze_audio_file
from models.gemini import analyze_audio_with_gemini, rewriter
from models.lyria import generate_music_with_lyria
from state.state import AppState

cfg = Default()


@me.page(path="/lyria", title="Lyria - GenMedia Creative Studio")
def lyria_page():
    """Main Page."""
    state = me.state(AppState)
    with page_scaffold(page_name="lyria"):  # pylint: disable=not-context-manager
        lyria_content(state)


@me.stateclass
class AudioMetricsState:
    mean_pitch_hz: float = 0.0
    pitch_std_hz: float = 0.0
    pitch_range_hz: float = 0.0
    jitter_percent: float = 0.0
    shimmer_db: float = 0.0
    hnr_db: float = 0.0
    estimated_tempo_bpm: float = 0.0
    duration_sec: float = 0.0


@me.stateclass
class PageState:
    """Local Page State"""

    is_loading: bool = False  # Generic loading state for Lyria generation or Rewriter
    is_analyzing: bool = False  # Specific loading state for Gemini analysis

    loading_operation_message: str = ""  # Message to display during is_loading

    music_prompt_input: str = ""
    music_prompt_placeholder: str = ""
    original_user_prompt: str = ""
    music_prompt_textarea_key: int = 0
    music_gcs_uri: str = ""
    music_display_url: str = ""

    timing: str = ""

    show_error_dialog: bool = False
    error_message: str = ""

    audio_analysis_result_json: str | None = None
    analysis_error_message: str = ""

    info_dialog_open: bool = False

    audio_metrics: AudioMetricsState = field(default_factory=AudioMetricsState)
    has_audio_metrics: bool = False


# Original box style
_BOX_STYLE = me.Style(
    background=me.theme_var("background"),
    border_radius=12,
    box_shadow=("0 3px 1px -2px #0003, 0 2px 2px #00000024, 0 1px 5px #0000001f"),
    padding=me.Padding(top=16, left=16, right=16, bottom=16),
    display="flex",
    flex_direction="column",
)

# Combined style for the analysis display box
_ANALYSIS_BOX_STYLE = me.Style(
    background=me.theme_var("background"),
    border_radius=12,
    box_shadow=("0 3px 1px -2px #0003, 0 2px 2px #00000024, 0 1px 5px #0000001f"),
    padding=me.Padding(top=16, left=16, right=16, bottom=16),
    display="flex",
    flex_direction="column",
    margin=me.Margin(top=16),
)

# Combined style for the analysis error display box
_ANALYSIS_ERROR_BOX_STYLE = me.Style(
    background=me.theme_var("background"),
    border_radius=12,
    padding=me.Padding(top=16, left=16, right=16, bottom=16),
    display="flex",
    flex_direction="column",
    margin=me.Margin(top=16),
    border=me.Border.all(me.BorderSide(color=me.theme_var("error"), width=1)),
)


def lyria_content(app_state: me.state):
    """Lyria Mesop Page"""
    pagestate = me.state(PageState)

    if pagestate.info_dialog_open:
        with dialog(is_open=pagestate.info_dialog_open):  # pylint: disable=not-context-manager
            me.text("About Lyria", type="headline-6")
            me.markdown(ABOUT_PAGE_CONTENT["sections"][2]["description"])
            me.divider()
            me.text("Current Settings", type="headline-6")
            me.text(f"Prompt: {pagestate.music_prompt_input}")
            with dialog_actions():  # pylint: disable=not-context-manager
                me.button("Close", on_click=close_info_dialog, type="flat")

    with page_frame():  # pylint: disable=not-context-manager
        header(
            "Lyria", "music_note", show_info_button=True, on_info_click=open_info_dialog,
        )

        with me.box(style=_BOX_STYLE):
            me.text(
                "Prompt for music generation",
                style=me.Style(font_weight=500),
            )
            me.box(style=me.Style(height=16))
            subtle_lyria_input()

        me.box(style=me.Style(height=24))

        # Primary Operation Loading Indicator (Lyria Generation or Rewriter)
        if pagestate.is_loading:
            with me.box(
                style=me.Style(
                    display="grid",
                    justify_content="center",
                    justify_items="center",
                    padding=me.Padding.all(16),
                ),
            ):
                me.progress_spinner()
                me.text(
                    pagestate.loading_operation_message,  # Display dynamic loading message
                    style=me.Style(margin=me.Margin(top=8)),
                )

        # Audio Player - Show if URI exists AND primary loading is done
        if (
            pagestate.music_display_url
            and not pagestate.is_loading  # Check generic loading
            and not pagestate.show_error_dialog
        ):
            with me.box(
                style=me.Style(
                    display="grid",
                    justify_content="center",
                    justify_items="center",
                    margin=me.Margin(bottom=16),
                ),
            ):
                me.audio(src=pagestate.music_display_url)

        # Gemini Analysis Loading Indicator - Show if analyzing AND primary loading is done
        if pagestate.is_analyzing and not pagestate.is_loading:
            with me.box(
                style=me.Style(
                    display="grid",
                    justify_content="center",
                    justify_items="center",
                    padding=me.Padding.all(16),
                ),
            ):
                me.progress_spinner()
                me.text(
                    "Analyzing audio with Gemini...",
                    style=me.Style(margin=me.Margin(top=8)),
                )

        # Analysis Display Area
        if (
            pagestate.audio_analysis_result_json
            and not pagestate.is_analyzing
            and not pagestate.is_loading
        ):
            try:
                analysis = json.loads(pagestate.audio_analysis_result_json)
                with me.box(style=_ANALYSIS_BOX_STYLE):
                    me.text(
                        "Music Critic",
                        type="headline-5",
                        style=me.Style(margin=me.Margin(bottom=12)),
                    )
                    if analysis.get("genre-quality"):
                        with me.box(style=me.Style(margin=me.Margin(bottom=10))):
                            genre_list = analysis["genre-quality"]

                            if isinstance(genre_list, list):
                                with me.box(
                                    style=me.Style(
                                        display="flex",
                                        flex_direction="row",
                                        gap=5,
                                        margin=me.Margin(bottom=5, top=10),
                                    ),
                                ):
                                    # me.text(
                                    #    "Genres / Qualities:",
                                    #    style=me.Style(font_weight=450),
                                    # )
                                    for item in genre_list:
                                        pill(item, pill_type="genre")
                            else:
                                me.text(str(genre_list))

                    with me.box(
                        style=me.Style(
                            margin=me.Margin(bottom=10),
                            display="flex",
                            flex_direction="row",
                            gap=5,
                        ),
                    ):
                        if analysis.get("audio-analysis"):
                            with me.box(
                                style=me.Style(
                                    flex=1,
                                    margin=me.Margin(bottom=10),
                                    padding=me.Padding(right=10),
                                ),
                            ):
                                me.text(
                                    "Description", style=me.Style(font_weight="bold"),
                                )
                                me.markdown(analysis["audio-analysis"])

                        if analysis.get("prompt-alignment"):
                            with me.box(
                                style=me.Style(
                                    flex=1,
                                    margin=me.Margin(bottom=10),
                                    padding=me.Padding(left=10),
                                ),
                            ):
                                me.text(
                                    "Prompt Alignment",
                                    style=me.Style(font_weight="bold"),
                                )
                                me.markdown(analysis["prompt-alignment"])

            except json.JSONDecodeError:
                with me.box(style=_ANALYSIS_ERROR_BOX_STYLE):
                    me.text(
                        "Audio Analysis Failed",
                        type="headline-6",
                        style=me.Style(
                            color=me.theme_var("error"), margin=me.Margin(bottom=12),
                        ),
                    )
                    me.text("Error: Could not display analysis data (invalid format).")

        # Analysis Error Display
        elif (
            pagestate.analysis_error_message
            and not pagestate.is_analyzing
            and not pagestate.is_loading
        ):
            with me.box(style=_ANALYSIS_ERROR_BOX_STYLE):
                me.text(
                    "Audio Analysis Failed",
                    type="headline-6",
                    style=me.Style(
                        color=me.theme_var("error"), margin=me.Margin(bottom=12),
                    ),
                )
                me.text(pagestate.analysis_error_message)

        # Technical Metrics Display
        if (
            pagestate.has_audio_metrics
            and not pagestate.is_analyzing
            and not pagestate.is_loading
        ):
            with me.box(style=_ANALYSIS_BOX_STYLE), me.expansion_panel(
                title="Technical Audio Metrics", icon="graphic_eq",
            ):
                metrics = pagestate.audio_metrics
                with me.box(
                    style=me.Style(
                        display="grid",
                        grid_template_columns="1fr 1fr",
                        gap=16,
                        padding=me.Padding.all(16),
                    ),
                ):
                    me.text(
                        f"Duration: {metrics.duration_sec:.2f}s",
                        style=me.Style(font_weight="bold"),
                    )
                    me.text(
                        f"Tempo: {metrics.estimated_tempo_bpm:.1f} BPM",
                        style=me.Style(font_weight="bold"),
                    )
                    me.text(f"Mean Pitch: {metrics.mean_pitch_hz:.1f} Hz")
                    me.text(f"Pitch Range: {metrics.pitch_range_hz:.1f} Hz")

        # Error Dialog for Generation Errors (Lyria errors)
        with dialog(is_open=pagestate.show_error_dialog):  # pylint: disable=not-context-manager
            me.text(
                "Generation Error",
                type="headline-6",
                style=me.Style(color=me.theme_var("error"), font_weight="bold"),
            )
            me.text(pagestate.error_message, style=me.Style(margin=me.Margin(top=16)))
            with dialog_actions():  # pylint: disable=not-context-manager
                me.button("Close", on_click=on_close_error_dialog, type="flat")


@me.component
def subtle_lyria_input():
    """Lyria music description input component"""
    pagestate = me.state(PageState)
    icon_style = me.Style(
        display="flex",
        flex_direction="column",
        gap=2,
        font_size=10,
        align_items="center",
    )
    with me.box(
        style=me.Style(
            border_radius=16,
            padding=me.Padding.all(8),
            background=me.theme_var("secondary-container"),
            display="flex",
            width="100%",
        ),
    ):
        with me.box(style=me.Style(flex_grow=1)):
            me.native_textarea(
                autosize=True,
                min_rows=8,
                placeholder="enter a musical audio description",
                style=me.Style(
                    padding=me.Padding(top=16, left=16, right=16, bottom=16),
                    background=me.theme_var("secondary-container"),
                    outline="none",
                    width="100%",
                    overflow_y="auto",
                    border=me.Border.all(me.BorderSide(style="none")),
                    color=me.theme_var("foreground"),
                    flex_grow=1,
                ),
                on_blur=on_blur_lyria_prompt,
                key=str(pagestate.music_prompt_textarea_key),
                value=pagestate.music_prompt_placeholder,
            )
        with me.box(
            style=me.Style(
                display="flex",
                flex_direction="column",
                gap=10,
                padding=me.Padding(left=16, right=16, bottom=16),
            ),
        ):
            with me.content_button(
                type="icon",
                on_click=on_click_lyria,
                disabled=pagestate.is_loading or pagestate.is_analyzing,
            ), me.box(style=icon_style):
                me.icon("music_note")
                me.text("Generate Audio")
            me.box(style=me.Style(height=5))
            with me.content_button(
                type="icon",
                on_click=on_click_lyria_rewriter,
                disabled=pagestate.is_loading or pagestate.is_analyzing,
            ), me.box(style=icon_style):
                me.icon("auto_awesome")
                me.text("Rewrite")
            me.box(style=me.Style(height=5))
            with me.content_button(
                type="icon",
                on_click=clear_music,
                disabled=pagestate.is_loading or pagestate.is_analyzing,
            ), me.box(style=icon_style):
                me.icon("clear")
                me.text("Clear")


def on_blur_lyria_prompt(e: me.InputBlurEvent):
    state = me.state(PageState)
    if not state.is_loading and not state.is_analyzing:
        state.music_prompt_input = e.value
        state.music_prompt_placeholder = e.value
        state.original_user_prompt = e.value
        state.audio_analysis_result_json = None
        state.analysis_error_message = ""
        state.loading_operation_message = ""


def on_click_lyria_rewriter(e: me.ClickEvent):
    state = me.state(PageState)
    prompt_to_rewrite = state.music_prompt_input
    if not prompt_to_rewrite:
        state.error_message = "Please enter a prompt before rewriting."
        state.show_error_dialog = True
        yield
        return
    if not state.original_user_prompt:
        state.original_user_prompt = prompt_to_rewrite

    state.is_loading = True
    state.loading_operation_message = (
        "Music rewriter in progress..."  # Set specific message
    )
    state.show_error_dialog = False
    state.error_message = ""
    state.audio_analysis_result_json = None
    state.analysis_error_message = ""
    yield

    try:
        rewritten_prompt = rewriter(prompt_to_rewrite, MUSIC_REWRITER)
        state.music_prompt_input = rewritten_prompt
        state.music_prompt_placeholder = rewritten_prompt
    except Exception as err:
        print(f"Error during prompt rewriting: {err}")
        state.error_message = str(err)
        state.show_error_dialog = True
    finally:
        state.is_loading = False
        state.loading_operation_message = ""  # Clear message
        yield


def on_click_lyria(e: me.ClickEvent):
    """Generate music with Lyria handler"""
    app_state = me.state(AppState)
    state = me.state(PageState)
    prompt_for_api = state.music_prompt_input
    if not prompt_for_api:
        state.error_message = "Music prompt cannot be empty."
        state.show_error_dialog = True
        yield
        return

    state.is_loading = True
    state.loading_operation_message = (
        "Generating music with Lyria..."  # Set specific message
    )
    state.music_upload_uri = ""
    state.show_error_dialog = False
    state.error_message = ""
    state.audio_analysis_result_json = None
    state.analysis_error_message = ""
    yield

    print(f"Let's make music with: {prompt_for_api}")
    if state.original_user_prompt and state.original_user_prompt != prompt_for_api:
        print(f"Original user prompt was: {state.original_user_prompt}")

    start_time = time.time()
    generated_successfully = False
    lyria_error_message_for_metadata = ""
    gcs_uri_for_analysis_and_metadata = ""
    analysis_dict_for_metadata = None

    try:
        destination_blob_path = generate_music_with_lyria(prompt_for_api)
        gcs_uri_for_analysis_and_metadata = destination_blob_path
        state.music_gcs_uri = destination_blob_path
        state.music_display_url = create_display_url(destination_blob_path)

        print(f"Music generated: {state.music_display_url}")
        generated_successfully = True
    except Exception as err:
        print(f"Error during music generation: {err}")
        state.error_message = str(err)
        lyria_error_message_for_metadata = str(err)
        state.show_error_dialog = True
    finally:
        state.is_loading = False
        state.loading_operation_message = ""  # Clear message
        yield

    if generated_successfully and gcs_uri_for_analysis_and_metadata:
        state.is_analyzing = True
        yield

        # --- Technical Audio Analysis ---
        try:
            print(
                f"Starting technical audio analysis for: {gcs_uri_for_analysis_and_metadata}",
            )
            metrics = analyze_audio_file(gcs_uri_for_analysis_and_metadata)
            state.audio_metrics.mean_pitch_hz = metrics.mean_pitch_hz
            state.audio_metrics.pitch_std_hz = metrics.pitch_std_hz
            state.audio_metrics.pitch_range_hz = metrics.pitch_range_hz
            state.audio_metrics.jitter_percent = metrics.jitter_percent
            state.audio_metrics.shimmer_db = metrics.shimmer_db
            state.audio_metrics.hnr_db = metrics.hnr_db
            state.audio_metrics.estimated_tempo_bpm = metrics.estimated_tempo_bpm
            state.audio_metrics.duration_sec = metrics.duration_sec
            state.has_audio_metrics = True
            print("Technical audio analysis successful.")
        except Exception as tech_err:
            print(f"Warning: Technical audio analysis failed: {tech_err}")
            # Don't fail the whole process, just log it.

        # --- Gemini Analysis ---
        try:
            print(
                f"Starting analysis with GCS URI: {gcs_uri_for_analysis_and_metadata}",
            )
            analysis_result_dict = analyze_audio_with_gemini(
                audio_uri=gcs_uri_for_analysis_and_metadata,
                music_generation_prompt=prompt_for_api,
            )
            if analysis_result_dict:
                state.audio_analysis_result_json = json.dumps(analysis_result_dict)
                analysis_dict_for_metadata = analysis_result_dict
                print(
                    f"Analysis successful, stored as JSON. Dict: {analysis_result_dict}",
                )
            else:
                state.analysis_error_message = "Analysis returned no result."
                print(state.analysis_error_message)

        except Exception as analysis_err:
            print(f"Error during audio analysis: {analysis_err}")
            state.analysis_error_message = f"Analysis failed: {analysis_err!s}"
        finally:
            state.is_analyzing = False
            yield

    end_time = time.time()
    execution_time = end_time - start_time
    state.timing = f"Generation time: {round(execution_time)} seconds"
    print(
        f"Total process (generation + analysis attempt) took: {execution_time:.2f} seconds",
    )

    logged_original_prompt = state.original_user_prompt
    logged_rewritten_prompt = ""
    if state.original_user_prompt and prompt_for_api != state.original_user_prompt:
        logged_rewritten_prompt = prompt_for_api
    elif not state.original_user_prompt and prompt_for_api:
        logged_original_prompt = prompt_for_api

    try:
        print(
            f"Logging to metadata: API Prompt='{prompt_for_api}', Original='{logged_original_prompt}', Rewritten='{logged_rewritten_prompt}'",
        )
        item = MediaItem(
            user_email=app_state.user_email,
            timestamp=datetime.datetime.now(datetime.UTC),
            prompt=prompt_for_api,
            original_prompt=logged_original_prompt,
            rewritten_prompt=logged_rewritten_prompt
            if logged_rewritten_prompt
            else None,
            model=cfg.LYRIA_MODEL_VERSION,
            mime_type="audio/wav",  # Lyria generates WAV
            generation_time=execution_time,
            error_message=lyria_error_message_for_metadata
            if lyria_error_message_for_metadata
            else None,
            gcsuri=gcs_uri_for_analysis_and_metadata
            if generated_successfully and gcs_uri_for_analysis_and_metadata
            else None,
            audio_analysis=json.dumps(analysis_dict_for_metadata)
            if analysis_dict_for_metadata
            else None,
            # duration might be available if analysis_dict_for_metadata contains it, or if Lyria API provides it
        )
        add_media_item_to_firestore(item)
    except Exception as meta_err:
        print(f"CRITICAL: Failed to store metadata: {meta_err}")


def clear_music(e: me.ClickEvent):
    state = me.state(PageState)
    state.music_prompt_input = ""
    state.music_prompt_placeholder = ""
    state.original_user_prompt = ""
    state.music_prompt_textarea_key += 1
    state.music_gcs_uri = ""
    state.music_display_url = ""
    state.is_loading = False
    state.is_analyzing = False
    state.show_error_dialog = False
    state.error_message = ""
    state.timing = ""
    state.audio_analysis_result_json = None
    state.analysis_error_message = ""
    state.loading_operation_message = ""  # Clear loading message
    state.has_audio_metrics = False
    # Reset metrics
    state.audio_metrics.mean_pitch_hz = 0.0
    state.audio_metrics.pitch_std_hz = 0.0
    state.audio_metrics.pitch_range_hz = 0.0
    state.audio_metrics.jitter_percent = 0.0
    state.audio_metrics.shimmer_db = 0.0
    state.audio_metrics.hnr_db = 0.0
    state.audio_metrics.estimated_tempo_bpm = 0.0
    state.audio_metrics.duration_sec = 0.0
    yield


def on_close_error_dialog(e: me.ClickEvent):
    state = me.state(PageState)
    state.show_error_dialog = False
    state.error_message = ""
    yield


def open_info_dialog(e: me.ClickEvent):
    """Open the info dialog."""
    state = me.state(PageState)
    state.info_dialog_open = True
    yield


def close_info_dialog(e: me.ClickEvent):
    """Close the info dialog."""
    state = me.state(PageState)
    state.info_dialog_open = False
    yield
