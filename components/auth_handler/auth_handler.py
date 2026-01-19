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
import typing

@me.web_component(path="./auth_handler.js")
def auth_handler(
    *,
    firebase_config: dict[str, str],
    on_auth_state_change: typing.Callable[[me.WebEvent], None],
    auto_login: bool = False,
    error_message: str = "",
    cached_photo_url: str = "",
    key: str | None = None,
):
    """
    Handles Firebase Authentication.
    """
    return me.insert_web_component(
        key=key,
        name="auth-handler",
        properties={
            "firebaseConfig": firebase_config,
            "autoLogin": auto_login,
            "errorMessage": error_message,
            "cachedPhotoUrl": cached_photo_url,
        },
        events={
            "authStateChange": on_auth_state_change,
        },
    )
