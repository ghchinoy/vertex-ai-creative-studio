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

"""A test page for comparing signed URL vs. proxy caching performance."""

from dataclasses import field

import mesop as me

from common.metadata import MediaItem, get_media_for_page
from common.utils import create_display_url
from components.header import header
from components.page_scaffold import page_frame, page_scaffold


@me.stateclass
class PageState:
    media_items: list[MediaItem] = field(default_factory=list)
    is_loading: bool = True


def on_load(e: me.LoadEvent):
    """Fetches the most recent images on page load."""
    state = me.state(PageState)
    if not state.media_items:
        state.is_loading = True
        yield
        # get_media_for_page returns a single list of items, not a tuple to be unpacked.
        items = get_media_for_page(
            page=1, media_per_page=15, type_filters=["images"], sort_by_timestamp=True,
        )

        if items:
            state.media_items = items
        else:
            state.media_items = []

        state.is_loading = False
        yield


@me.page(
    path="/test_proxy_caching",
    title="Proxy Caching Test",
    on_load=on_load,
)
def page():
    """Render the test page."""
    with page_scaffold(page_name="test_proxy_caching"), page_frame():
        header("Proxy Caching vs. Signed URLs", "cached")
        page_content()


def page_content():
    """Main content of the test page."""
    state = me.state(PageState)

    me.markdown(
        """This page demonstrates the performance difference between two methods of displaying private GCS images.

- **Signed URLs:** Secure but not cacheable by the browser. Notice how they re-download every time you reload the page.
- **Proxy Endpoint:** Secure and cacheable. Notice how they load instantly from the browser cache on the second page load.""",
    )

    if state.is_loading:
        me.progress_spinner()
        return

    with me.box(style=me.Style(margin=me.Margin(top=24))):
        # Method 1: Signed URLs (Not Cached)
        me.text(
            "Method 1: `USE_MEDIA_PROXY=False` (Direct GCS links, not cached by proxy)",
            type="headline-5",
        )
        with me.box(
            style=me.Style(
                display="flex", flex_wrap="wrap", gap=16, margin=me.Margin(top=16),
            ),
        ):
            for item in state.media_items:
                gcs_uri = item.gcsuri or (item.gcs_uris[0] if item.gcs_uris else None)
                if gcs_uri:
                    me.image(
                        src=create_display_url(gcs_uri),
                        style=me.Style(
                            height=150, width=150, object_fit="cover", border_radius=8,
                        ),
                    )

    with me.box(style=me.Style(margin=me.Margin(top=32))):
        # Method 2: Proxy Endpoint
        me.text(
            "Method 2: `USE_MEDIA_PROXY=True` (Proxy Endpoint, cached)",
            type="headline-5",
        )
        with me.box(
            style=me.Style(
                display="flex", flex_wrap="wrap", gap=16, margin=me.Margin(top=16),
            ),
        ):
            for item in state.media_items:
                gcs_uri = item.gcsuri or (item.gcs_uris[0] if item.gcs_uris else None)
                if gcs_uri:
                    me.image(
                        src=create_display_url(gcs_uri),
                        style=me.Style(
                            height=150, width=150, object_fit="cover", border_radius=8,
                        ),
                    )
