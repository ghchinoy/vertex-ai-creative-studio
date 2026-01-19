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

import datetime
from collections.abc import Callable
from dataclasses import dataclass

import mesop as me

from components.dialog import dialog
from components.header import header
from components.media_tile.media_tile import media_tile
from components.page_scaffold import page_frame, page_scaffold
from config.firebase_config import FirebaseClient
from state.admin_state import AdminState
from state.state import AppState


# Adapted from pages/config.py
@dataclass
class Tab:
    key: str
    label: str
    icon: str | None = None


def on_tab_change(e: me.ClickEvent):
    state = me.state(AdminState)
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


@me.page(
    path="/admin",
    title="Admin Dashboard - GenMedia Creative Studio",
)
def page():
    """Admin Dashboard Page."""
    app_state = me.state(AppState)

    # Secure the page: Only admins can view
    if app_state.role != "admin":
        me.navigate("/forbidden")
        return

    with page_scaffold(page_name="admin"), page_frame():
        header("Admin Dashboard", "admin_panel_settings")

        admin_content()


def admin_content():
    state = me.state(AdminState)

    with me.box(style=me.Style(margin=me.Margin(top=20))):
        tabs = [
            Tab(key="users", label="Users", icon="people"),
            Tab(key="logs", label="Unauthorized Logs", icon="history_toggle_off"),
        ]
        _tab_group(
            tabs=tabs,
            on_tab_click=on_tab_change,
            selected_tab_key=state.active_tab,
        )

        if state.active_tab == "users":
            users_tab()
        else:
            logs_tab()

    add_user_dialog()
    edit_user_dialog()


def users_tab():
    state = me.state(AdminState)

    with me.box(
        style=me.Style(
            display="flex",
            justify_content="space-between",
            align_items="center",
            margin=me.Margin(bottom=16),
        ),
    ):
        me.text("Authorized Users", type="headline-6")
        with me.content_button(
            on_click=lambda e: setattr(state, "show_add_user_dialog", True),
            type="raised",
        ), me.box(style=me.Style(display="flex", align_items="center", gap=8)):
            me.icon("person_add")
            me.text("Add User")

    # Fetch users from Firestore
    try:
        db = FirebaseClient().get_client()
        users_ref = db.collection("users").order_by("email")
        users = [doc.to_dict() for doc in users_ref.stream()]

        with me.box(style=me.Style(overflow_x="auto")):
            with me.box(
                style=me.Style(
                    display="grid",
                    grid_template_columns="50px 2fr 1fr 1.5fr 1.5fr 80px",
                    gap=16,
                    padding=me.Padding.all(12),
                    border=me.Border(
                        bottom=me.BorderSide(width=1, style="solid", color="#eee"),
                    ),
                    font_weight="bold",
                ),
            ):
                me.text("")
                me.text("Email")
                me.text("Role")
                me.text("First Joined")
                me.text("Last Signed In")
                me.text("Actions")

            for user in users:
                email = user.get("email", "N/A")
                role = user.get("role", "creator")
                first_signed_in = user.get("first_signed_in")
                last_signed_in = user.get("last_signed_in")
                photo_url = user.get("photo_url")
                gcs_avatar_uri = user.get("gcs_avatar_uri")

                # For native me.image, we MUST provide an HTTPS URL.
                # If it's a gs:// URI, we route it through our internal media proxy
                # to avoid 403 Forbidden errors on private buckets.
                avatar_url = photo_url  # Fallback to the Google URL
                if gcs_avatar_uri:
                    avatar_url = gcs_avatar_uri

                if not avatar_url:
                    avatar_url = "https://www.gstatic.com/images/branding/product/2x/avatar_anonymous_48dp.png"

                with me.box(
                    key=email,
                    on_click=on_user_row_click,
                    style=me.Style(
                        display="grid",
                        grid_template_columns="50px 2fr 1fr 1.5fr 1.5fr 80px",
                        gap=16,
                        padding=me.Padding.all(12),
                        align_items="center",
                        border=me.Border(
                            bottom=me.BorderSide(
                                width=1, style="solid", color="#f9f9f9",
                            ),
                        ),
                        cursor="pointer",
                    ),
                ):
                    with me.box(style=me.Style(width=32, height=32)):
                        media_tile(
                            media_type="image",
                            https_url=avatar_url,
                        )
                    me.text(email)
                    me.text(role, style=me.Style(font_style="italic"))
                    me.text(
                        first_signed_in.strftime("%Y-%m-%d %H:%M")
                        if isinstance(first_signed_in, datetime.datetime)
                        else "N/A",
                    )
                    me.text(
                        last_signed_in.strftime("%Y-%m-%d %H:%M")
                        if isinstance(last_signed_in, datetime.datetime)
                        else "Never",
                    )
                    with me.content_button(on_click=on_delete_user, key=email):
                        me.icon("delete", style=me.Style(color=me.theme_var("error")))

    except Exception as e:
        me.text(
            f"Error loading users: {e}", style=me.Style(color=me.theme_var("error")),
        )


def on_user_row_click(e: me.ClickEvent):
    state = me.state(AdminState)
    state.selected_user_email = e.key
    # Default to creator or current role? Let's just open the dialog
    state.show_edit_user_dialog = True
    yield


def edit_user_dialog():
    state = me.state(AdminState)
    with dialog(is_open=state.show_edit_user_dialog, key="edit_user_dialog"):
        me.text("Edit User Profile", type="headline-5")

        with me.box(
            style=me.Style(
                display="flex",
                flex_direction="column",
                gap=16,
                margin=me.Margin(top=20),
            ),
        ):
            me.text(
                f"User: {state.selected_user_email}", style=me.Style(font_weight="bold"),
            )

            with me.box(style=me.Style(display="flex", flex_direction="column", gap=8)):
                me.text("Update Role", style=me.Style(font_size=12, color="#666"))
                me.select(
                    label="Select Role",
                    options=[
                        me.SelectOption(label="Creator", value="creator"),
                        me.SelectOption(label="Builder", value="builder"),
                        me.SelectOption(label="Admin", value="admin"),
                    ],
                    on_selection_change=lambda e: setattr(
                        state, "new_user_role", e.value,
                    ),
                )

            if state.error_message:
                me.text(
                    state.error_message,
                    style=me.Style(color=me.theme_var("error"), font_size=12),
                )

            with me.box(
                style=me.Style(
                    display="flex",
                    justify_content="flex-end",
                    gap=10,
                    margin=me.Margin(top=10),
                ),
            ):
                me.button(
                    "Cancel",
                    on_click=lambda e: setattr(state, "show_edit_user_dialog", False),
                )
                me.button("Save Changes", on_click=on_confirm_edit_user, type="raised")


def on_confirm_edit_user(e: me.ClickEvent):
    state = me.state(AdminState)
    try:
        db = FirebaseClient().get_client()
        user_ref = db.collection("users").document(state.selected_user_email)
        user_ref.update(
            {"role": state.new_user_role, "updated_at": datetime.datetime.utcnow()},
        )

        state.show_edit_user_dialog = False
        state.error_message = ""
        # Clear the lru_cache for this email to ensure immediate effect
        from common.auth import get_user_role, is_user_authorized

        get_user_role.cache_clear()
        is_user_authorized.cache_clear()
        yield
    except Exception as ex:
        state.error_message = f"Error: {ex}"
        yield


def logs_tab():
    try:
        db = FirebaseClient().get_client()
        logs_ref = (
            db.collection("unauthorized_access_logs")
            .order_by("timestamp", direction="DESCENDING")
            .limit(50)
        )
        logs = [doc.to_dict() for doc in logs_ref.stream()]

        with me.box(style=me.Style(overflow_x="auto")):
            with me.box(
                style=me.Style(
                    display="grid",
                    grid_template_columns="2fr 1.5fr 2fr",
                    gap=16,
                    padding=me.Padding.all(12),
                    border=me.Border(
                        bottom=me.BorderSide(width=1, style="solid", color="#eee"),
                    ),
                    font_weight="bold",
                ),
            ):
                me.text("Email")
                me.text("Timestamp")
                me.text("Reason")

            for log in logs:
                with me.box(
                    style=me.Style(
                        display="grid",
                        grid_template_columns="2fr 1.5fr 2fr",
                        gap=16,
                        padding=me.Padding.all(12),
                        border=me.Border(
                            bottom=me.BorderSide(
                                width=1, style="solid", color="#f9f9f9",
                            ),
                        ),
                    ),
                ):
                    me.text(log.get("email", "N/A"))
                    ts = log.get("timestamp")
                    me.text(
                        ts.strftime("%Y-%m-%d %H:%M:%S")
                        if isinstance(ts, datetime.datetime)
                        else "N/A",
                    )
                    me.text(log.get("reason", "N/A"))

    except Exception as e:
        me.text(f"Error loading logs: {e}", style=me.Style(color=me.theme_var("error")))


def add_user_dialog():
    state = me.state(AdminState)
    with dialog(is_open=state.show_add_user_dialog, key="add_user_dialog"):
        me.text("Add New Authorized User", type="headline-5")

        with me.box(
            style=me.Style(
                display="flex",
                flex_direction="column",
                gap=16,
                margin=me.Margin(top=20),
            ),
        ):
            me.input(
                label="Email Address",
                on_blur=lambda e: setattr(state, "new_user_email", e.value),
            )

            with me.box(style=me.Style(display="flex", flex_direction="column", gap=8)):
                me.text("Role", style=me.Style(font_size=12, color="#666"))
                me.select(
                    label="Select Role",
                    options=[
                        me.SelectOption(label="Creator", value="creator"),
                        me.SelectOption(label="Builder", value="builder"),
                        me.SelectOption(label="Admin", value="admin"),
                    ],
                    on_selection_change=lambda e: setattr(
                        state, "new_user_role", e.value,
                    ),
                )

            if state.error_message:
                me.text(
                    state.error_message,
                    style=me.Style(color=me.theme_var("error"), font_size=12),
                )

            with me.box(
                style=me.Style(
                    display="flex",
                    justify_content="flex-end",
                    gap=10,
                    margin=me.Margin(top=10),
                ),
            ):
                me.button(
                    "Cancel",
                    on_click=lambda e: setattr(state, "show_add_user_dialog", False),
                )
                me.button("Add User", on_click=on_confirm_add_user, type="raised")


def on_confirm_add_user(e: me.ClickEvent):
    state = me.state(AdminState)
    if not state.new_user_email or "@" not in state.new_user_email:
        state.error_message = "Please enter a valid email address."
        return

    try:
        db = FirebaseClient().get_client()
        user_ref = db.collection("users").document(state.new_user_email)
        user_ref.set(
            {
                "email": state.new_user_email,
                "role": state.new_user_role,
                "added_at": datetime.datetime.utcnow(),
            },
            merge=True,
        )

        state.show_add_user_dialog = False
        state.new_user_email = ""
        state.error_message = ""
        yield
    except Exception as ex:
        state.error_message = f"Error: {ex}"
        yield


def on_delete_user(e: me.ClickEvent):
    email = e.key
    try:
        db = FirebaseClient().get_client()
        db.collection("users").document(email).delete()
        yield
    except Exception as ex:
        print(f"Error deleting user: {ex}")
        yield
