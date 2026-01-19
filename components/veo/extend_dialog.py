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

import time
from dataclasses import dataclass

import mesop as me
import requests

from common.analytics import track_model_call
from common.utils import create_display_url
from components.dialog import dialog, dialog_actions
from config.default import Default
from config.veo_models import VEO_MODELS, get_veo_model_config
from models.requests import VideoGenerationRequest
from state.state import AppState

config = Default()


@me.stateclass
@dataclass
class VeoExtendDialogState:
    is_open: bool = False
    is_loading: bool = False
    error_message: str = ""

    # Input
    input_video_uri: str = ""  # GCS Path
    prompt: str = ""
    duration: int = 8
    model_id: str = "3.1-fast"  # Default to 3.1 Fast

    # Output
    generated_video_uri: str = ""
    current_job_id: str = ""
    job_status: str = ""


@me.component
def extend_dialog(state: VeoExtendDialogState, on_close):
    """A dialog for extending an existing Veo video."""
    with dialog(is_open=state.is_open):
        me.text("Extend Video with Veo", type="headline-5")

        with me.box(
            style=me.Style(
                display="flex", flex_direction="row", gap=24, margin=me.Margin(top=16),
            ),
        ):
            # Left Column: Input Video Preview
            with me.box(style=me.Style(flex_basis="300px")):
                me.text("Input Video", type="subtitle-2")
                if state.input_video_uri:
                    me.video(
                        src=create_display_url(state.input_video_uri),
                        style=me.Style(
                            width="100%", border_radius=8, margin=me.Margin(top=8),
                        ),
                    )
                else:
                    me.text("No video selected.")

            # Right Column: Controls
            with me.box(
                style=me.Style(
                    flex_grow=1, display="flex", flex_direction="column", gap=16,
                ),
            ):
                # Prompt
                me.textarea(
                    label="Extension Prompt",
                    placeholder="Describe what happens next...",
                    on_blur=on_prompt_blur,
                    style=me.Style(width="100%"),
                )

                # Model Selection (Only show models that support extension)
                extension_models = [m for m in VEO_MODELS if m.supports_video_extension]
                me.select(
                    label="Veo Model",
                    options=[
                        me.SelectOption(label=m.display_name, value=m.version_id)
                        for m in extension_models
                    ],
                    value=state.model_id,
                    on_selection_change=on_model_change,
                )

                # Duration
                model_config = get_veo_model_config(state.model_id)
                if model_config and model_config.supported_extension_durations:
                    me.select(
                        label="Extension Duration",
                        options=[
                            me.SelectOption(label=f"{d}s", value=str(d))
                            for d in model_config.supported_extension_durations
                        ],
                        value=str(state.duration),
                        on_selection_change=on_duration_change,
                    )

        if state.error_message:
            me.text(
                state.error_message,
                style=me.Style(color=me.theme_var("error"), margin=me.Margin(top=16)),
            )

        if state.is_loading:
            with me.box(
                style=me.Style(
                    display="flex",
                    align_items="center",
                    gap=16,
                    margin=me.Margin(top=16),
                ),
            ):
                me.progress_spinner()
                me.text(f"Status: {state.job_status}...")

        with dialog_actions():
            me.button("Cancel", on_click=on_close, disabled=state.is_loading)
            me.button(
                "Generate Extension",
                on_click=on_click_generate_extension,
                type="raised",
                disabled=state.is_loading or not state.prompt,
            )


def on_prompt_blur(e: me.InputBlurEvent):
    state = me.state(VeoExtendDialogState)
    state.prompt = e.value


def on_model_change(e: me.SelectSelectionChangeEvent):
    state = me.state(VeoExtendDialogState)
    state.model_id = e.value
    # Reset duration to model default if needed
    model_config = get_veo_model_config(e.value)
    if model_config and model_config.supported_extension_durations:
        state.duration = model_config.supported_extension_durations[0]


def on_duration_change(e: me.SelectSelectionChangeEvent):
    state = me.state(VeoExtendDialogState)
    state.duration = int(e.value)


def on_click_generate_extension(e: me.ClickEvent):
    """Initiates the asynchronous video extension process."""
    state = me.state(VeoExtendDialogState)
    app_state = me.state(AppState)

    state.is_loading = True
    state.error_message = ""
    state.job_status = "starting"
    yield

    current_model_config = get_veo_model_config(state.model_id)

    # Prepare the request
    # NOTE: In extension mode, resolution and aspect ratio are typically
    # inherited from the source video, but for now we'll use defaults or model values.
    request = VideoGenerationRequest(
        prompt=state.prompt,
        model_version_id=state.model_id,
        aspect_ratio="16:9",  # Default
        resolution="1080p",  # Default
        duration_seconds=state.duration,
        video_count=1,
        enhance_prompt=True,
        generate_audio=True,
        person_generation="Allow (Adults only)",
        video_input_gcs=state.input_video_uri,
        video_input_mime_type="video/mp4",
    )

    # 1. Start the Async Job
    try:
        api_url = f"{config.API_BASE_URL}/api/veo/generate_async"
        headers = {"X-Goog-Authenticated-User-Email": app_state.user_email}

        with track_model_call(
            model_name=current_model_config.model_name,
            prompt_length=len(request.prompt),
            duration_seconds=request.duration_seconds,
            aspect_ratio=request.aspect_ratio,
            video_count=request.video_count,
            mode="extension",
        ):
            response = requests.post(
                api_url, json=request.model_dump(), headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        state.current_job_id = data["job_id"]
        state.job_status = data["status"]
        yield
    except Exception as ex:
        state.error_message = f"Failed to start extension: {ex}"
        state.is_loading = False
        yield
        return

    # 2. Poll for Completion
    start_time = time.time()
    while state.job_status in ["pending", "processing", "created", "starting"]:
        time.sleep(3)
        try:
            status_url = f"{config.API_BASE_URL}/api/veo/job/{state.current_job_id}"
            resp = requests.get(status_url)
            resp.raise_for_status()
            status_data = resp.json()
            state.job_status = status_data["status"]

            if state.job_status == "complete":
                # Success!
                state.generated_video_uri = (
                    status_data.get("video_uri")
                    or status_data.get("video_uris", [""])[0]
                )
                state.is_loading = False
                yield
                break
            elif state.job_status == "failed":
                state.error_message = status_data.get(
                    "error_message", "Generation failed.",
                )
                state.is_loading = False
                yield
                break

            # Still working...
            yield

        except Exception as ex:
            state.error_message = f"Polling failed: {ex}"
            state.is_loading = False
            yield
            break
