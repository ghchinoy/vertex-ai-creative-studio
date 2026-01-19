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

import base64
import uuid

import mesop as me

from common.metadata import MediaItem, add_media_item_to_firestore
from common.storage import store_to_gcs
from common.utils import create_display_url
from components.page_scaffold import page_scaffold
from components.selfie_camera.selfie_camera import selfie_camera
from state.state import AppState


@me.stateclass
class PageState:
    captured_image_url: str = ""
    is_saving: bool = False
    show_camera: bool = False


def on_capture(e: me.WebEvent):
    """Handle the capture event from the selfie camera component."""
    state = me.state(PageState)
    app_state = me.state(AppState)

    state.is_saving = True
    yield

    try:
        # The data URL is in the format: data:image/png;base64,iVBORw0KGgo...
        # We need to strip the header to get the pure base64 data.
        header, encoded = e.value["value"].split(",", 1)
        image_data = base64.b64decode(encoded)

        # Generate a unique filename
        filename = f"selfie-{uuid.uuid4()}.png"

        # Store the image to GCS
        gcs_uri = store_to_gcs(
            "selfie_captures",
            filename,
            "image/png",
            image_data,
        )

        # Create a MediaItem and save it to Firestore
        item = MediaItem(
            gcs_uris=[gcs_uri],
            prompt="Selfie capture",
            mime_type="image/png",
            user_email=app_state.user_email,
            comment="captured by selfie camera",
        )
        add_media_item_to_firestore(item)

        state.captured_image_url = create_display_url(gcs_uri)

    except Exception as ex:
        print(f"ERROR: Failed to save selfie. Details: {ex}")
    finally:
        state.is_saving = False
        yield


@me.page(path="/selfie", title="Selfie Capture")
def page():
    """Define the Mesop page route for Selfie Capture."""
    state = me.state(PageState)

    with page_scaffold(page_name="selfie"):  # pylint: disable=E1129:not-context-manager
        with me.box(
            style=me.Style(
                padding=me.Padding.all(24),
                display="flex",
                flex_direction="column",
                align_items="center",
                gap=16,
            ),
        ):
            me.text("Selfie Capture", type="headline-5")

            if state.show_camera:
                selfie_camera(on_capture=on_capture)
            else:
                me.button(
                    "Start Camera",
                    on_click=lambda e: setattr(state, "show_camera", True),
                    type="raised",
                )

            if state.is_saving:
                me.progress_spinner()
                me.text("Saving image...")

            if state.captured_image_url:
                me.text("Captured Image:")
                me.image(
                    src=state.captured_image_url,
                    style=me.Style(width=400, border_radius=12),
                )
