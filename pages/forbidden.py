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

import mesop as me

from state.state import AppState


@me.page(
    path="/forbidden",
    title="Access Denied - GenMedia Creative Studio",
)
def page():
    """Simple Forbidden page with no extra components to prevent redirect loops."""
    app_state = me.state(AppState)

    with me.box(
        style=me.Style(
            display="flex",
            flex_direction="column",
            align_items="center",
            justify_content="center",
            height="100vh",
            background=me.theme_var("background"),
            font_family="'Google Sans', Roboto, sans-serif",
        ),
    ):
        me.icon(
            "lock",
            style=me.Style(
                font_size=64,
                height=64,
                width=64,
                color=me.theme_var("error"),
            ),
        )

        me.text(
            "Access Denied",
            type="headline-4",
            style=me.Style(margin=me.Margin(top=24, bottom=16)),
        )

        me.text(
            f"Sorry, {app_state.user_email}, you do not have permission to access this application.",
            type="headline-6",
            style=me.Style(
                text_align="center",
                padding=me.Padding.symmetric(horizontal=40),
            ),
        )

        me.text(
            "Please contact an administrator to be added to the allowlist.",
            style=me.Style(margin=me.Margin(top=16, bottom=40)),
        )

        # Simple button that takes them back to welcome.
        # The user can sign out there if they need to switch accounts.
        me.button(
            "Go Back",
            on_click=lambda e: me.navigate("/welcome"),
            type="stroked",
        )
