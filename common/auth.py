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
"""Authentication and Authorization utilities."""

from datetime import UTC, datetime
from functools import lru_cache

from config.default import Default as DefaultConfig
from config.firebase_config import FirebaseClient


@lru_cache(maxsize=1024)
def _check_user_auth_cached(email: str) -> tuple[bool, str]:
    """Internal cached check for user authorization.

    Returns (is_authorized, reason).
    """
    if not email or email == "anonymous@google.com":
        return False, "Anonymous user"

    # 1. Check Firestore "users" collection (Primary source of truth)
    db_client = FirebaseClient()
    database_id = getattr(db_client, "database_id", "default")
    try:
        db = db_client.get_client()
        user_ref = db.collection("users").document(email)
        user_doc = user_ref.get()
        if user_doc.exists:
            return True, f"Authorized via Firestore (DB: {database_id})"
    except Exception as e:  # noqa: BLE001
        print(
            f"AuthZ error checking Firestore (DB: {database_id}) for {email}: {e}",
            flush=True,
        )

    # 2. Check Domain Allowlist Fallback
    allowlist_str = DefaultConfig().DOMAIN_ALLOWLIST
    if allowlist_str:
        allowed_domains = [d.strip().lower() for d in allowlist_str.split(",")]
        user_domain = email.split("@")[-1].lower()
        if user_domain in allowed_domains:
            return True, "Authorized via domain allowlist"

    return False, "Domain and Firestore check failed"


def is_user_authorized(email: str) -> bool:
    """Check if a user is authorized based on their domain or Firestore allowlist.

    Logs unauthorized attempts for audit purposes.
    """
    is_authorized, reason = _check_user_auth_cached(email)

    db_client = FirebaseClient()
    database_id = getattr(db_client, "database_id", "default")

    if is_authorized:
        print(f"DEBUG: User {email} authorized: {reason}", flush=True)
        return True

    # Log Unauthorized Attempt
    print(
        f"DEBUG: User {email} NOT authorized (DB: {database_id}). Reason: {reason}",
        flush=True,
    )
    try:
        db = db_client.get_client()
        db.collection("unauthorized_access_logs").add(
            {
                "email": email,
                "timestamp": datetime.now(UTC),
                "reason": reason,
                "domain_allowlist_configured": bool(DefaultConfig().DOMAIN_ALLOWLIST),
                "database_id": database_id,
            },
        )
    except Exception as e:  # noqa: BLE001
        print(f"Error logging unauthorized attempt for {email}: {e}", flush=True)

    return False


def get_user_avatar(email: str) -> str | None:
    """Retrieve the cached GCS avatar URI for a user from Firestore."""
    if not email or email == "anonymous@google.com":
        return None
    db_client = FirebaseClient()
    database_id = getattr(db_client, "database_id", "default")
    try:
        db = db_client.get_client()
        user_doc = db.collection("users").document(email).get()
        if user_doc.exists:
            return user_doc.to_dict().get("gcs_avatar_uri")
    except Exception as e:  # noqa: BLE001
        print(f"Error fetching avatar for {email} (DB: {database_id}): {e}", flush=True)
    return None


@lru_cache(maxsize=1024)
def get_user_role(email: str) -> str:
    """Retrieve the user's role from Firestore, defaulting to 'creator'."""
    if not email or email == "anonymous@google.com":
        return "guest"
    db_client = FirebaseClient()
    database_id = getattr(db_client, "database_id", "default")
    try:
        db = db_client.get_client()
        user_doc = db.collection("users").document(email).get()
        if user_doc.exists:
            role = user_doc.to_dict().get("role", "creator")
            print(
                f"DEBUG: Found role '{role}' for user '{email}' (DB: {database_id})",
                flush=True,
            )
            return role
        print(
            f"DEBUG: No user document found for '{email}' (DB: {database_id}), defaulting to 'creator'",
            flush=True,
        )
    except Exception as e:  # noqa: BLE001
        print(f"Error fetching role for {email} (DB: {database_id}): {e}", flush=True)
    return "creator"
