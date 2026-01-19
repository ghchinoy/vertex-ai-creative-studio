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
"""Common methods"""

from config.default import reference_voices


def get_uri_by_key_name(name: str, key_name: str):
    """Gets the key value for a given voice name.

    Args:
      reference_voices: A list of dictionaries, where each dictionary represents a voice
                         and has "name" and "uri" keys.
      name: The name of the voice to search for.

    Returns:
      The URI of the voice if found, or None if not found.

    """
    for voice in reference_voices:
        if voice["name"] == name:
            return voice[key_name]
    return None
