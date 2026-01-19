"""Simple snackbar component that is similar to Angular Component Snackbar."""

import time
from collections.abc import Callable
from typing import Literal

import mesop as me

from state.state import AppState

## Example usage
# snackbar(
#     label="Cannonball!!!",
#     action_label="Splash",
#     on_click_action=on_click_snackbar_close,
#     is_visible=state.is_visible,
#     horizontal_position=state.horizontal_position,  # type: ignore
#     vertical_position=state.vertical_position,  # type: ignore
# )

# me.button(
#     "Trigger snackbar",
#     type="flat",
#     color="primary",
#     on_click=on_click_snackbar_open,
# )


def on_horizontal_position_change(e: me.SelectSelectionChangeEvent):
    state = me.state(AppState)
    state.toast_horizontal_position = e.value


def on_vertical_position_change(e: me.SelectSelectionChangeEvent):
    state = me.state(AppState)
    state.toast_vertical_position = e.value


def on_duration_change(e: me.SelectSelectionChangeEvent):
    state = me.state(AppState)
    state.toast_duration = int(e.value)


def on_click_snackbar_close(e: me.ClickEvent):
    state = me.state(AppState)
    state.toast_is_visible = False


def on_click_snackbar_open(e: me.ClickEvent):
    state = me.state(AppState)
    state.toast_is_visible = True

    # Use yield to create a timed snackbar message.
    if state.toast_duration:
        yield
        time.sleep(state.toast_duration)
        state.toast_is_visible = False
        yield
    else:
        yield


@me.component
def snackbar(
    *,
    is_visible: bool,
    label: str,
    action_label: str | None = None,
    on_click_action: Callable | None = None,
    horizontal_position: Literal["start", "center", "end"] = "center",
    vertical_position: Literal["start", "center", "end"] = "end",
):
    """Creates a snackbar.

    By default the snackbar is rendered at bottom center.

    The on_click_action should typically close the snackbar as part of its actions. If no
    click event is included, you'll need to manually hide the snackbar.

    Note that there is one issue with this snackbar example. No actions are possible when
    using "time.sleep and yield" to imitate a status message that fades away after a
    period of time.

    Args:
      is_visible: Whether the snackbar is currently visible or not.
      label: Message for the snackbar
      action_label: Optional message for the action of the snackbar
      on_click_action: Optional click event when action is triggered.
      horizontal_position: Horizontal position of the snackbar
      vertical_position: Vertical position of the snackbar

    """
    print(f"visible {is_visible}, label {label}, action {action_label}")

    with me.box(
        style=me.Style(
            display="block" if is_visible else "none",
            height="100%",
            overflow_x="auto",
            overflow_y="auto",
            position="relative",
            pointer_events="none",
            width="100%",
            z_index=1000,
        ),
    ), me.box(
        style=me.Style(
            align_items=vertical_position,
            height="100%",
            display="flex",
            justify_content=horizontal_position,
        ),
    ), me.box(
        style=me.Style(
            align_items="center",
            background=me.theme_var("on-surface-variant"),
            border_radius=5,
            box_shadow=(
                "0 3px 1px -2px #0003, 0 2px 2px #00000024, 0 1px 5px #0000001f"
            ),
            display="flex",
            font_size=14,
            justify_content="space-between",
            margin=me.Margin.all(10),
            padding=(
                me.Padding(top=5, bottom=5, right=5, left=15)
                if action_label
                else me.Padding.all(15)
            ),
            pointer_events="auto",
            width=300,
        ),
    ):
        me.text(
            label,
            style=me.Style(color=me.theme_var("surface-container-lowest")),
        )
        if action_label:
            me.button(
                action_label,
                on_click=on_click_action,
                style=me.Style(color=me.theme_var("primary-container")),
            )
