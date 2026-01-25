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
"""Firebase client singleton."""

from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore


class FirebaseClient:
    """Firebase client singleton class."""

    _instance = None
    _client = None
    database_id: str | None = None

    def __new__(cls, database_id: str | None = None) -> "FirebaseClient":
        """Create or return the singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize(database_id)
        return cls._instance

    def _initialize(self, database_id: str | None = None) -> None:
        """Initialize the Firebase Admin SDK and Firestore client."""
        try:
            self.database_id = database_id
            cred = credentials.ApplicationDefault()
            firebase_admin.initialize_app(cred)
            print(
                f"[FirebaseClient] - initiating firebase client with `{database_id}`",
            )
        except ValueError:
            print("[FirebaseClient] - Firebase already initialized.")
        self._client = firestore.client(database_id=database_id)

    def get_client(self) -> Any:  # noqa: ANN401
        """Return the Firestore client instance."""
        return self._client
