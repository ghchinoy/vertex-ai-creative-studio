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
"""About Babel Mesop Page"""

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
            "Babel generates audio for the text input in all Google Cloud Text to Speech Chirp 3: HD voice locales.",
        )

        me.html(
            """Made by <img src='static/aaie_logo.png' height='16px'> Google Cloud's <b>Applied AI Engineering</b>
        """,
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
                me.text(f"Chirp 3: HD Voices ({len(state.voices)})", type="headline-6")

                me.html(
                    "<a href='https://cloud.google.com/text-to-speech/docs/voice-types' target='_blank'>Chirp 3: HD voices</a> and <a href='https://cloud.google.com/text-to-speech/docs/voices' target='_blank'>all Cloud TTS voices</a>",
                )
                sorted_voices = sorted(state.voices, key=lambda voice: voice["name"])
                for voice in sorted_voices:
                    me.text(
                        f"{voice.get('name')} / {voice['gender']} / {voice['language_codes'][0]}",
                    )


def settings_page(app_state: me.state):
    """Babel's Settings page"""
    state = me.state(AppState)
    with me.box(style=CONTENT_STYLE):
        me.text("Settings", type="headline-6")

        me.text(
            "Gemini Translation Prompt (simple)",
            style=me.Style(font_weight="bold"),
        )

        me.markdown(
            text="""```
Translate the following statement into appropriate vernacular in language {{ .ISO639-1-Language-Code }}.

Statement:
{{ .Statement}} 

Output only the statement mimicing the level of formality, do not explain why.

Translation: 
```""",
        )

        me.box(style=me.Style(height="60px"))

        me.text("Welcome Voices", style=me.Style(font_weight="bold"))

        with me.box(
            style=me.Style(
                display="flex",
                flex_direction="row",
                gap=5,
            ),
        ):
            for idx, voice in enumerate(reference_voices):
                name = voice.get("name")
                if "Leda" in name or "Puck" in name:
                    me.checkbox(f"Chirp 3: HD {name}", checked=True, disabled=True)
                else:
                    me.checkbox(f"Chirp 3: HD {name}", checked=False, disabled=True)

        me.box(style=me.Style(height="16px"))

        me.text("Explore Voices", style=me.Style(font_weight="bold"))

        with me.box(
            style=me.Style(
                display="flex",
                flex_direction="row",
                gap=5,
            ),
        ):
            for idx, voice in enumerate(reference_voices):
                name = voice.get("name")
                if "Leda" in name or "Puck" in name:
                    me.checkbox(f"Chirp 3: HD {name}", checked=True, disabled=True)
                else:
                    me.checkbox(f"Chirp 3: HD {name}", checked=False, disabled=True)

        me.box(style=me.Style(height="16px"))

        me.text("Voice Family Choices", style=me.Style(font_weight="bold"))
        with me.box(style=me.Style(display="flex", flex_direction="column")):
            me.checkbox("Chirp 3: HD", checked=True, disabled=True)
            me.checkbox("Chirp HD", checked=False, disabled=True)

            # sorted_voices = sorted(state.voices, key=lambda voice: voice["name"])
            # for voice in sorted_voices:
            #    me.checkbox(
            #        f"{voice["name"]} ({voice["gender"]})", checked=True, disabled=True
            #    )


def on_click_set_gemini_voice(e: me.ClickEvent):
    """Event to set the gemini voice"""
    state = me.state(AppState)
    state.gemini_voice = e.key
    print(f"voice choice: {e.key}")
    uri = get_uri_by_key_name(e.key, "uri")
    if uri:
        print(f"the gsuri is: {uri}")
        state.gemini_reference_voice_uri = uri.replace(
            "gs://",
            "https://storage.mtls.cloud.google.com/",
        )
    else:
        print("Couldn't find URI for voice")
