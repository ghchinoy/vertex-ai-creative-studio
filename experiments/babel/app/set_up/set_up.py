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

import json
import logging
import urllib

import google.auth
import google.auth.transport.requests as googlerequests
import google.oauth2.id_token
from dotenv import load_dotenv

from config.default import Default, Voice

load_dotenv(override=True)
logging.basicConfig(level=logging.DEBUG)
config = Default()


class VoicesSetup:
    """Set up Journey Voices"""

    @staticmethod
    def init():
        """Initial population of voices"""
        return get_voices()


def get_voices():
    """Calls the backend endpoint for the list of available Journey Voices
    Sets this as a state variable for downstream use (display on About page
    and on Settings page)
    """
    split_url = urllib.parse.urlsplit(config.BABEL_ENDPOINT)
    VOICE_ENDPOINT = f"{split_url.scheme}://{split_url.netloc}/voices"  # pylint: disable=invalid-name
    req = urllib.request.Request(VOICE_ENDPOINT)
    print(f"VOICE_ENDPOINT: {VOICE_ENDPOINT}")

    if "localhost" not in VOICE_ENDPOINT:
        logging.info("calling remote endpoint")
        credentials, config.PROJECT_ID = google.auth.default()
        credentials.refresh(googlerequests.Request())

        urlinfo = urllib.parse.urlparse(VOICE_ENDPOINT)
        audience = f"{urlinfo.scheme}://{urlinfo.netloc}/"
        auth_req = google.auth.transport.requests.Request()
        id_token = google.oauth2.id_token.fetch_id_token(auth_req, audience)

        req.add_header("Authorization", f"Bearer {id_token}")
    else:
        logging.info("calling local endpoint")

    req.add_header("Content-Type", "application/json; charset=utf-8")
    response = urllib.request.urlopen(req)
    response_as_string = response.read().decode("utf-8")

    data = json.loads(response_as_string)
    logging.info("returned %s voices", len(data))
    return [Voice(item) for item in data]
