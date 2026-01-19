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
"""Gemini 2.0 Voices Studio Mesop Page"""

import json
import logging

# from typing import List, TypedDict, Any, cast
import urllib
from dataclasses import field

import google.auth
import google.auth.transport.requests as googlerequests
import google.oauth2.id_token
import mesop as me
from common.utility import get_uri_by_key_name

# from components.page_scaffold import page_scaffold, page_frame
from components.styles import BACKGROUND_COLOR, CONTENT_STYLE
from config.default import BabelMetadata, Default, gemini_voices

logging.basicConfig(level=logging.DEBUG)
config = Default()
BUCKET_PATH = "https://storage.mtls.cloud.google.com/" + config.GENMEDIA_BUCKET


@me.stateclass
class PageState:
    """Local Page State"""

    is_loading: bool = False

    gemini_voice: str = "Zephyr"
    gemini_statement: str = ""
    gemini_output_metadata: list[BabelMetadata] = field(default_factory=list)  # pylint: disable=invalid-field-call
    gemini_reference_voice_uri: str = ""
    gemini_reference_voice_image_uri: str = ""

    audio_output_infos: list[str] = field(default_factory=list)  # pylint: disable=invalid-field-call


# Gemini voices
def gemini_studio_page(app_state: me.state):
    """Gemini Studio page"""
    state = me.state(PageState)
    # print(f"{state.current_page}")
    # with me.box(style=me.Style(flex_direction="row", display="flex")):
    with me.box(style=CONTENT_STYLE):
        me.text("Enter text to voice", type="headline-6")
        with me.box(
            style=me.Style(
                display="flex",
                flex_direction="row",
                gap=3,
                align_items="flex-start",
                padding=me.Padding(bottom=16),
            ),
        ):
            me.image(
                src=state.gemini_reference_voice_image_uri,
                style=me.Style(height=56),
            )

            voice_options = []
            gemini_voices.sort()
            for voice in gemini_voices:
                voice_options.append(
                    me.SelectOption(
                        label=voice,
                        value=voice,
                    ),
                )

            me.select(
                label="Select a Gemini Voice",
                options=voice_options,
                on_selection_change=on_click_set_gemini_voice,
                value=state.gemini_voice,
            )

        subtle_chat_input_gemini()

        if state.is_loading:
            me.progress_spinner()
        elif state.gemini_output_metadata:
            with me.box(
                style=me.Style(display="grid", grid_template_columns="1fr 1fr"),
            ):
                sorted_metadata = sorted(
                    state.gemini_output_metadata,
                    key=lambda voice: voice["language_code"],
                )
                for item in sorted_metadata:
                    # print(item)
                    audio_url = f"{BUCKET_PATH}/{item['audio_path']}"
                    # print(audio_url)
                    with me.box(
                        style=me.Style(
                            display="flex",
                            flex_direction="column",
                            gap=5,
                            padding=me.Padding(top=10, left=10, right=10, bottom=12),
                        ),
                    ):
                        me.text(
                            f"{item['voice_name']}",
                            style=me.Style(font_weight="bold"),
                        )
                        me.audio(src=audio_url)
                        me.text(item["text"])


def on_click_set_gemini_voice(e: me.ClickEvent):
    """Event to set the gemini voice"""
    state = me.state(PageState)
    state.gemini_voice = e.value
    print(f"voice choice: {e.value}")

    uri = get_uri_by_key_name(e.value, "uri")
    if uri:
        # print(f"the gsuri is: {uri}")
        state.gemini_reference_voice_uri = uri.replace(
            "gs://", "https://storage.mtls.cloud.google.com/",
        )
    else:
        print("Couldn't find URI for voice")

    image = get_uri_by_key_name(e.value, "icon")
    if image:
        print(f"the image gsuri is: {image}")
        state.gemini_reference_voice_image_uri = uri.replace(
            "gs://", "https://storage.mtls.cloud.google.com/",
        )
    else:
        print("Couldn't find URI for voice")


@me.component
def subtle_chat_input_gemini():
    """Input component"""
    with me.box(
        style=me.Style(
            border_radius=16,
            padding=me.Padding.all(8),
            background=BACKGROUND_COLOR,
            display="flex",
            width="100%",
        ),
    ):
        with me.box(
            style=me.Style(
                flex_grow=1,
            ),
        ):
            me.native_textarea(
                autosize=True,
                min_rows=8,
                placeholder="Voicing instructions for Gemini",
                style=me.Style(
                    padding=me.Padding(top=16, left=16),
                    background=BACKGROUND_COLOR,
                    outline="none",
                    width="100%",
                    overflow_y="auto",
                    border=me.Border.all(
                        me.BorderSide(style="none"),
                    ),
                    color=me.theme_var("on-surface"),
                ),
                on_blur=on_blur_gemini_statement,
            )
        # with me.content_button(type="icon"):
        #  me.icon("upload")
        # with me.content_button(type="icon"):
        #  me.icon("photo")
        with me.content_button(type="icon", on_click=on_click_gemini):
            me.icon("send")


def on_blur_gemini_statement(e: me.InputBlurEvent):
    """Updates the statement to synthesize"""
    state = me.state(PageState)
    state.gemini_statement = e.value


def on_click_gemini(e: me.ClickEvent):
    """Uses the Gemini voices to create audio"""
    state = me.state(PageState)
    state.is_loading = True
    if not state.gemini_statement:
        print("no statement provided. not synthesizing.")
        return

    state.audio_output_infos.clear()
    yield

    post_object = {
        "statement": state.gemini_statement,
        # "instructions": "say the following",
        "voiceName": state.gemini_voice,
    }
    print(post_object)
    endpoint = f"{config.BABEL_ENDPOINT}/gemini"
    print(f"endpoint: {endpoint}")
    req = urllib.request.Request(endpoint)

    if "localhost" not in endpoint:
        credentials, project_id = google.auth.default()
        print(f"project id: {project_id}")
        credentials.refresh(googlerequests.Request())
        print(f"credentials.token {credentials.token}")

        urlinfo = urllib.parse.urlparse(endpoint)
        audience = f"{urlinfo.scheme}://{urlinfo.netloc}/"
        print(f"audience: {audience}")
        auth_req = google.auth.transport.requests.Request()
        id_token = google.oauth2.id_token.fetch_id_token(auth_req, audience)
        print(f"id token {id_token}")

        req.add_header("Authorization", f"Bearer {id_token}")

    try:
        req.add_header("Content-Type", "application/json; charset=utf-8")
        bindata = str(json.dumps(post_object)).encode("utf-8")
        response = urllib.request.urlopen(req, bindata)
        response_as_string = response.read().decode("utf-8")
        print(response_as_string)

        data = json.loads(response_as_string)

        # state.audio_output_uri = f"{BUCKET_PATH}{data.get("outputfiles")[0]}"
        # state.audio_output_infos.clear()
        # for f in data.get("audio_metadata"):
        #  state.audio_output_infos.append(f"{BUCKET_PATH}{f}")

        print(data.get("audio_metadata"))

        state.gemini_output_metadata.clear()
        state.gemini_output_metadata = [
            BabelMetadata(item) for item in data.get("audio_metadata")
        ]

    except urllib.error.HTTPError as err:
        print(f"HTTP Error: {err.code} - {err.reason}")
        # Handle the HTTP error (e.g., log it, retry the request, etc.)

    except urllib.error.URLError as err:
        print(f"URL Error: {err.reason}")
        # Handle the URL error (e.g., check network connectivity)

    except OSError as err:
        print(f"Socket Error: {err}")
        # Handle the socket error (e.g., retry the request, check network
        state.gemini_statement = ""

    state.is_loading = False
    yield
