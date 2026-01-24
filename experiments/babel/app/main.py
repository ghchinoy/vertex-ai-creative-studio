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
"""Babel Main Mesop Application"""

import os
from typing import TypedDict

# from dataclasses import field
import mesop as me

# from config.default import BabelMetadata, Voice
from fastapi import FastAPI
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.staticfiles import StaticFiles
from pages.chirphd_voices import chirphd_voices_page
from pages.explore import explore_page
from set_up.set_up import VoicesSetup

from pages.about import about_page, settings_page
from pages.welcome import welcome_page
from state.state import AppState

# set up Mesop to be hosted via FastAPI
app = FastAPI()

# mount static files
app.mount("/static", StaticFiles(directory="local_assets"), name="static")

# main FastAPI app
app.mount(
    "/",
    WSGIMiddleware(
        me.create_wsgi_app(debug_mode=os.environ.get("DEBUG_MODE", "") == "true"),
    ),
)


class Page(TypedDict):
    """Page structure"""

    id: int
    name: str
    page_definition: str


content_pages = [
    Page(name="home", page_definition="home_page"),
    Page(name="about", page_definition="about_page"),
    Page(name="settings", page_definition="settings_page"),
    Page(name="welcome", page_definiton="welcome_page"),
    Page(name="world_tour", page_definition="explore_page"),
]


def show_page(page_name: str):
    """Show page switcher"""
    match page_name:
        case "welcome":
            welcome_page_reference()
        case "world_tour":
            explore_page_reference()
        case "home":
            home_page()
        case "about":
            about_page_reference()
        case "settings":
            settings_page_reference()
        case _:
            about_page_reference()


def on_click_page_choice(e: me.ClickEvent):
    """Change state to current page"""
    state = me.state(AppState)
    print(f"Clicked on: {e.key}")
    page = next(
        (item for item in content_pages if item["name"] == e.key),
        state.current_page,
    )
    print(f"Found: {page}")
    print(f"current page: {page['name']}")
    state.current_page = page["name"]


def toggle_theme(e: me.ClickEvent):  # pylint: disable=unused-argument
    """Toggle theme event"""
    if me.theme_brightness() == "light":
        me.set_theme_mode("dark")
    else:
        me.set_theme_mode("light")


SIDENAV_MIN_WIDTH = 150
SIDENAV_MAX_WIDTH = 76


def on_click_menu(e: me.ClickEvent):  # pylint: disable=unused-argument
    """Menu click event handler"""
    state = me.state(AppState)
    state.sidenav_open = not state.sidenav_open


def load(e: me.LoadEvent):  # pylint: disable=unused-argument
    """Page load event"""
    # print("load event", e) # this event looks like: LoadEvent(path='/') or LoadEvent(path='/leaderboard')
    s = me.state(AppState)
    print("theme", s.theme_mode)
    if s.theme_mode:  # recall state theme mode
        me.set_theme_mode(s.theme_mode)
    else:
        me.set_theme_mode("system")

    # get_voices()
    s.voices = VoicesSetup.init()


@me.page(
    path="/",
    title="Fabulae: Babel",
    on_load=load,
)
def babel():
    """Main Mesop App Page: Chirp 3: HD Voices"""
    state = me.state(AppState)

    with me.box(
        style=me.Style(
            display="flex",
            flex_direction="column",
            height="100%",
        ),
    ):
        # header
        with me.box(
            style=me.Style(
                flex_direction="row",
                display="flex",
                gap=5,
                padding=me.Padding(top=10, left=10, right=10, bottom=0),
                align_items="",
                # background=me.theme_var("surface-container"),
                # border=me.Border(bottom=me.BorderSide(width="0.01em", style="solid", color="#c3c5dd",))
            ),
        ):
            with me.content_button(on_click=on_click_menu):
                me.icon("menu")
            me.text("Babel", type="headline-5")
            me.box(style=me.Style(width=10))
            me.button(
                label="Experiment",
                type="stroked",
                disabled="true",
                style=me.Style(
                    font_size="9pt",
                    height="25px",
                    color="grey",
                    text_transform="uppercase",
                ),
            )

            # with me.content_button(
            #  type="icon",
            #  style=me.Style(position="absolute", right=44, top=8),
            #  #on_click=link_to_feedback
            # ):
            #  me.icon("feedback")
            me.link(
                text="feedback",
                url="https://cloud.google.com/text-to-speech/docs/chirp3-hd",  # your feedback form URL here
                open_in_new_tab=True,
                style=me.Style(
                    position="absolute",
                    right=48,
                    top=18,
                    text_decoration="none",
                    color=me.theme_var("on-surface"),
                ),
            )

            with me.content_button(
                type="icon",
                style=me.Style(position="absolute", right=4, top=8),
                on_click=toggle_theme,
            ):
                me.icon(
                    "light_mode" if me.theme_brightness() == "dark" else "dark_mode",
                )
                # content area

        # side menu
        with (
            me.sidenav(
                opened=True,
                style=me.Style(
                    width=SIDENAV_MAX_WIDTH
                    if state.sidenav_open
                    else SIDENAV_MIN_WIDTH,
                    margin=me.Margin(top=60),
                    padding=me.Padding(top=10, left=5, right=5, bottom=0),
                    background=me.theme_var("surface-container-lowest"),
                    border_radius="0 30px 0 0",
                ),
            ),
            me.box(style=me.Style(display="flex", flex_direction="column")),
        ):
            # Home: Journey Voices
            with (
                me.content_button(
                    style=me.Style(align_content="start"),
                    on_click=on_click_page_choice,
                    key="home",
                ),
                me.box(
                    style=me.Style(
                        display="flex",
                        flex_direction="row",
                        gap=5,
                        align_items="center",
                    ),
                ),
            ):
                me.icon(
                    "equalizer",
                )
                if not state.sidenav_open:
                    me.text(
                        "Chirp 3: HD",
                    )

            with (
                me.content_button(
                    style=me.Style(align_content="start"),
                    on_click=on_click_page_choice,
                    key="welcome",
                ),
                me.box(
                    style=me.Style(
                        display="flex",
                        flex_direction="row",
                        gap=5,
                        align_items="center",
                    ),
                ),
            ):
                me.icon(
                    "spa",
                )
                if not state.sidenav_open:
                    me.text(
                        "Welcome",
                    )

            with (
                me.content_button(
                    style=me.Style(align_content="start"),
                    on_click=on_click_page_choice,
                    key="world_tour",
                ),
                me.box(
                    style=me.Style(
                        display="flex",
                        flex_direction="row",
                        gap=5,
                        align_items="center",
                    ),
                ),
            ):
                me.icon(
                    "explore",
                )
                if not state.sidenav_open:
                    me.text(
                        "Explore",
                    )

            # Bottom buttons
            with me.box(
                style=me.Style(
                    position="absolute",
                    bottom=8,
                ),
            ):
                # About
                with (
                    me.content_button(
                        style=me.Style(align_content="start"),
                        on_click=on_click_page_choice,
                        key="about",
                    ),
                    me.box(
                        style=me.Style(
                            display="flex",
                            flex_direction="row",
                            gap=5,
                            align_items="center",
                        ),
                    ),
                ):
                    me.icon(
                        "info",
                    )
                    if not state.sidenav_open:
                        me.text(
                            "About",
                        )

                # Settings
                with (
                    me.content_button(
                        style=me.Style(align_content="start"),
                        on_click=on_click_page_choice,
                        key="settings",
                    ),
                    me.box(
                        style=me.Style(
                            display="flex",
                            flex_direction="row",
                            gap=5,
                            align_items="center",
                        ),
                    ),
                ):
                    me.icon(
                        "settings",
                    )
                    if not state.sidenav_open:
                        me.text(
                            "Settings",
                        )

        # primary content
        with me.box(
            style=me.Style(
                margin=me.Margin(
                    left=SIDENAV_MAX_WIDTH if state.sidenav_open else SIDENAV_MIN_WIDTH,
                ),
                padding=me.Padding(top=10, left=10, right=10, bottom=0),
            ),
        ):
            show_page(state.current_page)


# Home: Journey voices
def home_page():
    """Journey Voices page"""
    chirphd_voices_page(me.state(AppState))


# About
def about_page_reference():
    """About page"""
    about_page(me.state(AppState))


# Settings
def settings_page_reference():
    """Settings Page"""
    settings_page(me.state(AppState))


# Welcome
def welcome_page_reference():
    """Welcome Page"""
    welcome_page(me.state(AppState))


# Explore
def explore_page_reference():
    """Describe Page"""
    explore_page(me.state(AppState))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_includes=["*.py", "*.js"],
        timeout_graceful_shutdown=0,
    )
