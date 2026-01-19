"""Component for displaying a single item in the storyboard.
"""

from collections.abc import Callable

import mesop as me

from common.utils import create_display_url


@me.component
def storyboard_item_tile(
    image_url: str,
    room_name: str,
    on_click: Callable,
    key: str,
):
    """A simple tile for displaying a storyboard item.
    """
    display_url = (
        create_display_url(image_url) if image_url.startswith("gs://") else image_url
    )
    with me.box(
        key=key,
        on_click=on_click,
        style=me.Style(
            width=200,
            height=150,
            border_radius=8,
            background=f"url({display_url}) center / cover",
            position="relative",
            cursor="pointer",
            border=me.Border.all(me.BorderSide(color=me.theme_var("outline-variant"))),
            flex_shrink=0,
        ),
    ), me.box(
        style=me.Style(
            position="absolute",
            bottom=0,
            left=0,
            right=0,
            background="rgba(0, 0, 0, 0.6)",
            padding=me.Padding(top=4, bottom=4, left=8, right=8),
            border_radius="0 0 8px 8px",
        ),
    ):
        me.text(
            room_name,
            style=me.Style(
                color="white",
                font_size=14,
                font_weight=500,
                overflow="hidden",
                text_overflow="ellipsis",
                white_space="nowrap",
            ),
        )
