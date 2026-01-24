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

import mesop as me
from state.veo_and_me_state import PageState

from components.image_thumbnail import image_thumbnail
from components.library.library_chooser_button import library_chooser_button


@me.component
def r2v_uploader(
    on_r2v_asset_add,
    on_r2v_asset_remove,
    on_r2v_style_add,
    on_r2v_style_remove,
    on_library_select,
):
    """A focused uploader for the Reference-to-Video (r2v) mode."""
    state = me.state(PageState)
    MAX_ASSET_IMAGES = 3

    # Determine if uploaders should be disabled
    style_uploader_disabled = bool(state.r2v_reference_images)
    asset_uploader_disabled = state.r2v_style_image is not None

    with me.box(style=me.Style(display="flex", flex_direction="row", gap=15)):
        # --- Assets Section ---
        with me.box(style=me.Style(display="flex", flex_direction="column", gap=2)):
            me.text("Asset references", style=me.Style(font_size="10pt"))
            with me.box(style=me.Style(display="flex", flex_direction="row", gap=5)):
                for i in range(MAX_ASSET_IMAGES):
                    if i < len(state.r2v_reference_images):
                        image_uri = state.r2v_reference_images[i]
                        image_thumbnail(
                            image_uri=image_uri,
                            index=i,
                            on_remove=on_r2v_asset_remove,
                            icon_size=16,
                        )
                    elif not asset_uploader_disabled and i == len(
                        state.r2v_reference_images,
                    ):
                        _uploader_placeholder(
                            on_upload=on_r2v_asset_add,
                            on_library_select=on_library_select,
                            key_prefix="r2v_asset",
                            disabled=asset_uploader_disabled,
                        )
                    else:
                        _empty_placeholder()
        # --- Style Section ---
        with me.box(style=me.Style(display="flex", flex_direction="column", gap=2)):
            me.text("Style reference", style=me.Style(font_size="10pt"))
            with me.box(style=me.Style(display="flex", flex_direction="row", gap=5)):
                if state.r2v_style_image:
                    image_thumbnail(
                        image_uri=state.r2v_style_image,
                        index=0,  # Only one style image
                        on_remove=on_r2v_style_remove,
                        icon_size=16,
                    )
                else:
                    _uploader_placeholder(
                        on_upload=on_r2v_style_add,
                        on_library_select=on_library_select,
                        key_prefix="r2v_style",
                        disabled=style_uploader_disabled,
                    )


@me.component
def _uploader_placeholder(
    on_upload,
    on_library_select,
    key_prefix: str,
    disabled: bool,
):
    """A placeholder box with uploader and library chooser buttons."""
    with me.box(
        style=me.Style(
            height=100,
            width=100,
            border=me.Border.all(
                me.BorderSide(
                    width=1,
                    style="dashed",
                    color=me.theme_var("outline"),
                ),
            ),
            border_radius=8,
            display="flex",
            flex_direction="column",
            align_items="center",
            justify_content="center",
            gap=8,
            opacity=0.5 if disabled else 1.0,
        ),
    ):
        me.uploader(
            label="Add Image",
            on_upload=on_upload,
            accepted_file_types=["image/jpeg", "image/png"],
            key=f"{key_prefix}_uploader",
            disabled=disabled,
        )
        with me.box(style=me.Style(pointer_events="none" if disabled else "auto")):
            library_chooser_button(
                key=f"{key_prefix}_library_chooser",
                on_library_select=on_library_select,
                button_type="icon",
            )


@me.component
def _empty_placeholder():
    """An empty, non-interactive placeholder box."""
    me.box(
        style=me.Style(
            height=100,
            width=100,
            border=me.Border.all(
                me.BorderSide(width=1, style="dashed", color=me.theme_var("outline")),
            ),
            border_radius=8,
            opacity=0.5,
        ),
    )
