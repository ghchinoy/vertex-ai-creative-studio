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
"""Settings Babel Mesop Page"""

import logging

import mesop as me
from common.utility import get_uri_by_key_name

from components.styles import CONTENT_STYLE
from config.default import Default, reference_voices
from state.state import AppState

logging.basicConfig(level=logging.DEBUG)
config = Default()


def about_page(app_state: me.state):
    """Babel's About page"""
    state = app_state
    with me.box(style=CONTENT_STYLE):
        me.text("About Babel", type="headline-6")
        me.text(
            "Babel generates audio for the text input in all Google Cloud Text to Speech Journey voice locales and also Gemini native audio voices.",
        )

        me.html(
            "Please provide feedback <a href='https://forms.gle/UorXGdPJ2QJ39gHg6' target='_blank'>via this form</a>",
        )

        me.html(
            "See also: <a href='http://go/babel-fabulae-about' target='_blank'>go/babel-fabulae-about</a>",
        )

        me.box(style=me.Style(height="16"))

        with me.box(
            style=me.Style(
                display="flex",
                flex_direction="row",
                flex_wrap="wrap",
                justify_content="space-evenly",
                # width="100wv",
                # flex_basis=1,
            ),
        ):
            with me.box():
                me.text(f"Journey Voices ({len(state.voices)})", type="headline-6")

                me.html(
                    "<a href='https://cloud.google.com/text-to-speech/docs/voice-types' target='_blank'>Journey voices</a> and <a href='https://cloud.google.com/text-to-speech/docs/voices' target='_blank'>all Cloud TTS voices</a>",
                )
                sorted_voices = sorted(state.voices, key=lambda voice: voice["name"])
                for voice in sorted_voices:
                    me.text(
                        f"{voice.get('name')} / {voice['gender']} / {voice['language_codes'][0]}",
                    )

            with me.box(
                style=me.Style(
                    display="flex",
                    flex_direction="column",
                    gap=10,
                    padding=me.Padding(bottom=10),
                ),
            ):
                me.text("Gemini Voices", type="headline-6")

                for idx, voice in enumerate(reference_voices):
                    name = voice.get("name")
                    with me.content_button(
                        on_click=on_click_set_gemini_voice,
                        key=name,
                    ):
                        with me.box(
                            style=me.Style(
                                display="flex",
                                flex_direction="row",
                                gap=5,
                                align_items="center",
                            ),
                        ):
                            me.image(
                                src=f"https://www.gstatic.com/roma/assets/voices/00{idx + 1}.png",
                                style=me.Style(height=56),
                            )
                            me.text(name)

                me.audio(
                    src=state.gemini_reference_voice_uri,
                    autoplay=True,
                )


def on_click_set_gemini_voice(e: me.ClickEvent):
    """Event to set the gemini voice"""
    state = me.state(AppState)
    state.gemini_voice = e.key
    print(f"voice choice: {e.key}")
    uri = get_uri_by_key_name(reference_voices, e.key)
    if uri:
        print(f"the gsuri is: {uri}")
        state.gemini_reference_voice_uri = uri.replace(
            "gs://",
            "https://storage.mtls.cloud.google.com/",
        )
    else:
        print("Couldn't find URI for voice")
