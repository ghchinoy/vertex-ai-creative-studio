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

import uuid
from functools import lru_cache

from fastapi import Request

from common.storage import get_or_create_session
from config.default import Default as cfg
from config.firebase_config import FirebaseClient


@lru_cache(maxsize=1024)
def is_user_authorized(email: str) -> bool:
    """Checks if a user is authorized based on their domain or Firestore allowlist.
    Logs unauthorized attempts for audit purposes.
    """
    if not email or email == "anonymous@google.com":
        return False

    # 1. Check Firestore "users" collection (Primary source of truth)
    try:
        db = FirebaseClient().get_client()
        user_ref = db.collection("users").document(email)
        user_doc = user_ref.get()
        if user_doc.exists:
            return True
    except Exception as e:
        print(f"AuthZ error checking Firestore for {email}: {e}")

    # 2. Check Domain Allowlist Fallback
    allowlist_str = cfg().DOMAIN_ALLOWLIST
    is_domain_authorized = False
    if allowlist_str:
        allowed_domains = [d.strip().lower() for d in allowlist_str.split(",")]
        user_domain = email.split("@")[-1].lower()
        if user_domain in allowed_domains:
            is_domain_authorized = True

    if is_domain_authorized:
        return True

    # 3. Log Unauthorized Attempt
    try:
        from datetime import datetime

        db = FirebaseClient().get_client()
        db.collection("unauthorized_access_logs").add(
            {
                "email": email,
                "timestamp": datetime.utcnow(),
                "reason": "Domain and Firestore check failed",
                "domain_allowlist_configured": bool(allowlist_str),
            },
        )
    except Exception as e:
        print(f"Error logging unauthorized attempt for {email}: {e}")

    return False


def get_user_avatar(email: str) -> str | None:
    """Retrieves the cached GCS avatar URI for a user from Firestore.
    """
    if not email or email == "anonymous@google.com":
        return None
    try:
        db = FirebaseClient().get_client()
        user_doc = db.collection("users").document(email).get()
        if user_doc.exists:
            return user_doc.to_dict().get("gcs_avatar_uri")
    except Exception as e:
        print(f"Error fetching avatar for {email}: {e}")
    return None


@lru_cache(maxsize=1024)
def get_user_role(email: str) -> str:
    """Retrieves the user's role from Firestore, defaulting to 'creator'.
    """
    if not email or email == "anonymous@google.com":
        return "guest"
    try:
        db = FirebaseClient().get_client()
        user_doc = db.collection("users").document(email).get()
        if user_doc.exists:
            role = user_doc.to_dict().get("role", "creator")
            print(f"DEBUG: Found role '{role}' for user '{email}'", flush=True)
            return role
        print(
            f"DEBUG: No user document found for '{email}', defaulting to 'creator'",
            flush=True,
        )
    except Exception as e:
        print(f"Error fetching role for {email}: {e}")
    return "creator"
