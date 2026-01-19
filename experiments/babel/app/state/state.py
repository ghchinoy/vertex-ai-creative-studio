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

from dataclasses import field

import mesop as me
from set_up.set_up import Voice


@me.stateclass
class AppState:
    """Mesop Application State"""

    theme_mode: str = "light"

    sidenav_open: bool = False

    # pylint: disable=invalid-field-call
    is_loading: bool = False
    sidenav_open: bool = False
    start_page: str = "home"
    current_page: str = "home"

    voices: list[Voice] = field(default_factory=list)

    toast_is_visible: bool = False
    toast_duration: int = 2
    toast_horizontal_position: str = "center"
    toast_vertical_position: str = "end"

    # pylint: disable=invalid-field-call
