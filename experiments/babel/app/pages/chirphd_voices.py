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
"""Journey Voices Mesop Page"""

import json
import logging

# from typing import List, TypedDict, Any, cast
import urllib
from dataclasses import field

import google.auth
import google.auth.transport.requests as googlerequests
import google.oauth2.id_token
import mesop as me

# from set_up.set_up import VoicesSetup
# from components.page_scaffold import page_scaffold, page_frame
from components.styles import BACKGROUND_COLOR, CONTENT_STYLE
from config.default import BabelMetadata, Default

logging.basicConfig(level=logging.DEBUG)
config = Default()
BUCKET_PATH = "https://storage.mtls.cloud.google.com/" + config.GENMEDIA_BUCKET


@me.stateclass
class PageState:
    """Local Page State"""

    is_loading: bool = False
    statement: str = ""
    audio_output_uri: str = ""
    audio_output_infos: list[str] = field(default_factory=list)  # pylint: disable=invalid-field-call
    audio_output_metadata: list[BabelMetadata] = field(default_factory=list)  # pylint: disable=invalid-field-call
    audio_status: str = ""


def chirphd_voices_page(app_state: me.state):
    """Chirp HD Voices page"""
    state = me.state(PageState)
    # app_state = me.state(app_state)

    # with page_scaffold():  # pylint: disable=not-context-manager
    #   with page_frame():  # pylint: disable=not-context-manager

    # print(f"{state.current_page}")
    # with me.box(style=me.Style(flex_direction="row", display="flex")):
    with me.box(style=CONTENT_STYLE):
        me.text("Enter text to voice", type="headline-6")
        me.text(
            f"Using {len(app_state.voices)} Chirp 3: HD voices",
            style=me.Style(font_style="italic"),
        )
        subtle_chat_input_journey()

        if state.is_loading:
            me.progress_spinner()
        elif state.audio_output_metadata:
            with me.box(
                style=me.Style(display="grid", grid_template_columns="1fr 1fr"),
            ):
                # for uri in state.audio_output_infos:
                #  me.audio(src=uri)
                sorted_metadata = sorted(
                    state.audio_output_metadata,
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
                            f"{item['language_code']} ({item['gender'].lower()}, {item['voice_name']})",
                            style=me.Style(font_weight="bold"),
                        )
                        me.audio(src=audio_url)
                        me.text(item["text"])


@me.component
def subtle_chat_input_journey():
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
                min_rows=4,
                placeholder="Statement to voice with Chirp 3: HD voices",
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
                on_blur=on_blur_statement,
            )
        # with me.content_button(type="icon"):
        #  me.icon("upload")
        # with me.content_button(type="icon"):
        #  me.icon("photo")
        with me.box(style=me.Style(display="flex", gap=5, flex_direction="column")):
            with me.content_button(type="icon", on_click=on_click_babel):
                me.icon("send")
            with me.content_button(type="icon", on_click=on_click_clear_babel):
                me.icon("clear")


def on_blur_statement(e: me.InputBlurEvent):
    """Updates the statement to synthesize"""
    state = me.state(PageState)
    state.statement = e.value


def on_click_clear_babel(e: me.ClickEvent):  # pylint: disable=unused-argument
    """Clear babel input event"""
    state = me.state(PageState)
    state.is_loading = False
    state.audio_output_infos.clear()
    state.audio_output_metadata.clear()


def on_click_babel(e: me.ClickEvent):  # pylint: disable=unused-argument
    """Invokes the babel endpoint

    Args:
        e (me.ClickEvent): event click

    """
    state = me.state(PageState)
    state.is_loading = True

    if not state.statement:
        print("no statement provided. not synthesizing.")
        return

    state.audio_output_infos.clear()
    yield

    post_object = {"statement": state.statement}
    print(post_object)
    endpoint = f"{config.BABEL_ENDPOINT}/babel"
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

    state.audio_output_metadata.clear()
    state.audio_output_metadata = [
        BabelMetadata(item) for item in data.get("audio_metadata")
    ]

    state.is_loading = False
    yield
