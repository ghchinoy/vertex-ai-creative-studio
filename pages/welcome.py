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

import json

import mesop as me

from common.analytics import log_page_view
from components.welcome_hero.welcome_hero import welcome_hero
from components.page_scaffold import on_theme_load, on_auth_state_change
from components.theme_manager.theme_manager import theme_manager
from components.auth_handler import auth_handler
from components.snackbar import snackbar
from common.auth import get_user_avatar
from common.utils import create_display_url
from config.default import Default as cfg
from state.state import AppState


@me.stateclass
class PageState:
    show_login: bool = False


def on_load(e: me.LoadEvent):
    """Handles page load."""
    yield


def on_tile_click(e: me.WebEvent):
    app_state = me.state(AppState)
    page_state = me.state(PageState)
    is_authenticated = (
        app_state.user_email and app_state.user_email != "anonymous@google.com"
    )

    if is_authenticated:
        route = e.value["route"]
        me.navigate(route)
    else:
        # Toggle state to trigger autoLogin in auth-handler
        page_state.show_login = True
    yield


@me.page(
    path="/welcome",
    title="Welcome - GenMedia Creative Studio",
    on_load=on_load,
    stylesheets=[
        "/assets/style.css",
    ],
)
def page():
    """Define the Mesop page route for the welcome page."""
    app_state = me.state(AppState)
    page_state = me.state(PageState)
    log_page_view(page_name="welcome", session_id=app_state.session_id)

    theme_manager(theme=app_state.theme_mode, on_theme_load=on_theme_load)

    # Wrap auth_handler in a high z-index box so it stays on top of the fixed hero
    with me.box(style=me.Style(position="fixed", top=0, right=0, z_index=1000, width="100%")):
        # Need auth_handler to handle the login event
        firebase_config = {
            "apiKey": cfg().FIREBASE_API_KEY,
            "authDomain": cfg().FIREBASE_AUTH_DOMAIN,
            "projectId": cfg().FIREBASE_PROJECT_ID,
            "storageBucket": cfg().FIREBASE_STORAGE_BUCKET,
            "messagingSenderId": cfg().FIREBASE_MESSAGING_SENDER_ID,
            "appId": cfg().FIREBASE_APP_ID,
            "measurementId": cfg().FIREBASE_MEASUREMENT_ID,
        }
        # Fetch cached avatar if it exists
        cached_avatar_uri = get_user_avatar(app_state.user_email)
        cached_photo_url = create_display_url(cached_avatar_uri) if cached_avatar_uri else ""

        auth_handler.auth_handler(
            firebase_config=firebase_config,
            on_auth_state_change=on_auth_state_change,
            auto_login=page_state.show_login,
            cached_photo_url=cached_photo_url,
        )

    tiles_data = [
        {"icon": "home", "route": "/home"},
        {"label": "Veo", "route": "/veo"},
        {"label": "Gemini Image Generation", "icon": "banana", "route": "/nano-banana"},
        {"label": "Lyria", "route": "/lyria"},
        {"label": "Speech", "route": "/home"},
        {"label": "Workflows", "route": "/home"},
    ]

    welcome_hero(
        title="GenMedia Creative Studio",
        subtitle="Fuel your creativity with Google Cloud Vertex AI's generative media models and custom workflows.",
        # video_url="https://deepmind.google/api/blob/website/media/veo__cover_s0RKXWX.mp4", # Veo 2.0 backup
        video_url="https://storage.googleapis.com/gdm-deepmind-com-prod-public/media/media/veo__page-cover-1_hcTy7l3.mp4",
        tiles=json.dumps(tiles_data),
        on_tile_click=on_tile_click,
    )
