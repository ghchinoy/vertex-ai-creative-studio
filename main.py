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
"""Main Mesop App."""

import datetime
import inspect
import os
import uuid

import google.auth
import mesop as me
from fastapi import APIRouter, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.wsgi import WSGIMiddleware
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from firebase_admin import auth
from google.auth import impersonated_credentials
from google.cloud import storage
from pydantic import BaseModel

from app_factory import app
from common.utils import create_display_url, mirror_user_avatar
from config import default as config
from config.firebase_config import FirebaseClient
from models.video_processing import convert_mp4_to_gif
from routers import veo_router

# Initialize Firebase Client with configured database
FirebaseClient(database_id=config.Default().GENMEDIA_FIREBASE_DB)
import pages  # noqa: F401
from common.auth import get_user_role, is_user_authorized
from pages import admin as admin_page
from pages.test_async_veo import page as test_async_veo_page
from pages.test_character_consistency import (
    page as test_character_consistency_page,
)
from pages.test_index import page as test_index_page
from pages.test_infinite_scroll import test_infinite_scroll_page
from pages.test_media_chooser import page as test_media_chooser_page
from pages.test_pixie_compositor import test_pixie_compositor_page
from pages.test_svg import test_svg_page
from pages.test_uploader import test_uploader_page
from pages.test_vto_prompt_generator import (
    page as test_vto_prompt_generator_page,
)
from workflows.retro_games import page as retro_games_page


class UserInfo(BaseModel):
    email: str | None
    agent: str | None


class LoginRequest(BaseModel):
    token: str | None
    photo_url: str | None = None


# FastAPI server with Mesop
router = APIRouter()
app.include_router(router)


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Verify Firebase ID token and set a session cookie."""
    if not request.token:
        print("DEBUG: login endpoint called without token", flush=True)
        response = JSONResponse(content={"status": "logged_out"})
        response.delete_cookie("session_token")
        return response

    db_client = FirebaseClient()
    database_id = getattr(db_client, "database_id", "default")

    try:
        # Verify the ID token
        try:
            decoded_token = auth.verify_id_token(request.token)
        except Exception as token_err:  # noqa: BLE001
            print(f"DEBUG: Token verification failed: {token_err}", flush=True)
            raise HTTPException(status_code=401, detail=f"Invalid token: {token_err}") from token_err

        email = decoded_token.get("email")

        # 1. Check if the user is authorized BEFORE creating/updating the record.
        # This prevents "self-registration" for unauthorized users.
        if email and is_user_authorized(email):
            # 2. Only update user record if authorized.
            try:
                db = db_client.get_client()
                user_ref = db.collection("users").document(email)
                user_doc = user_ref.get()

                now = datetime.datetime.now(datetime.UTC)
                update_data = {
                    "email": email,
                    "last_signed_in": now,
                }

                # Set first_signed_in if it doesn't exist (new or legacy user)
                if not user_doc.exists or "first_signed_in" not in (
                    user_doc.to_dict() or {}
                ):
                    update_data["first_signed_in"] = now

                if request.photo_url:
                    update_data["photo_url"] = request.photo_url
                    # Try to mirror the avatar to GCS
                    gcs_avatar_uri = mirror_user_avatar(
                        email,
                        request.photo_url,
                    )
                    if gcs_avatar_uri:
                        update_data["gcs_avatar_uri"] = gcs_avatar_uri

                # Use set with merge=True so we don't overwrite other fields like 'role'
                user_ref.set(update_data, merge=True)
                print(f"DEBUG: Updated user record for {email} (DB: {database_id})", flush=True)
            except Exception as e:  # noqa: BLE001
                print(f"Error updating user record for {email} (DB: {database_id}): {e}", flush=True)
        else:
            print(f"Unauthorized login attempt blocked for: {email} (DB: {database_id})", flush=True)
            raise HTTPException(status_code=403, detail="User not authorized")

        # Create a session cookie
        expires_in = datetime.timedelta(days=5)
        try:
            session_cookie = auth.create_session_cookie(
                request.token,
                expires_in=expires_in,
            )
        except Exception as cookie_err:  # noqa: BLE001
            print(f"DEBUG: Failed to create session cookie: {cookie_err}", flush=True)
            raise HTTPException(status_code=500, detail="Failed to create session") from cookie_err

        user_role = get_user_role(email)
        print(
            f"DEBUG: login endpoint returning role '{user_role}' for '{email}' (DB: {database_id})",
            flush=True,
        )

        response = JSONResponse(
            content={"status": "success", "role": user_role, "email": email},
        )
        response.set_cookie(
            key="session_token",
            value=session_cookie,
            expires=int(expires_in.total_seconds()),
            httponly=True,
            secure=True,  # Ensure this is True in production (HTTPS)
            samesite="Lax",
        )
        return response
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        print(f"Auth error in login: {e}", flush=True)
        raise HTTPException(status_code=401, detail="Authentication failed") from e


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("assets/favicon.ico")


# Define allowed origins for CORS
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.cloudshell\.dev|http://localhost:8080",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/convert_to_gif")
def convert_to_gif(gcs_uri: str, request: Request):
    """Converts an MP4 video to a GIF and saves it to GCS."""
    try:
        uri = convert_mp4_to_gif(gcs_uri, request.scope["MESOP_USER_EMAIL"])

        return {"url": create_display_url(uri)}
    except Exception as e:
        error_message = str(e)
        print(f"Error generating GIF: {error_message}")
        return {"error": error_message}, 500


@app.get("/api/get_signed_url")
def get_signed_url(gcs_uri: str):
    """Generates a signed URL for a GCS object."""
    try:
        credentials, _ = google.auth.default()

        signing_credentials = impersonated_credentials.Credentials(
            source_credentials=credentials,
            target_principal=config.Default.SERVICE_ACCOUNT_EMAIL,
            target_scopes="https://www.googleapis.com/auth/devstorage.read_only",
        )

        storage_client = storage.Client()
        bucket_name, blob_name = gcs_uri.replace("gs://", "").split("/", 1)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        signed_url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(minutes=15),
            method="GET",
            credentials=signing_credentials,
        )

        return {"signed_url": signed_url}
    except Exception as e:
        error_message = str(e)
        print(f"Error generating signed url: {error_message}")
        if "private key" in error_message:
            print(
                "This error often occurs in a local development environment. "
                "Please ensure you have authenticated with service account impersonation by running: "
                "gcloud auth application-default login --impersonate-service-account=<YOUR_SERVICE_ACCOUNT_EMAIL>",
            )
        return {"error": error_message}, 500


@app.middleware("http")
async def add_global_csp(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://esm.sh https://cdn.jsdelivr.net https://www.gstatic.com https://apis.google.com; "
        "connect-src 'self' https://esm.sh https://cdn.jsdelivr.net https://storage.cloud.google.com https://storage.googleapis.com https://*.googleusercontent.com https://*.googleapis.com https://*.firebaseio.com https://www.gstatic.com https://firebasestorage.googleapis.com; "
        "frame-src 'self' https://*.firebaseapp.com https://*.firebaseauth.com https://accounts.google.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com http://fonts.googleapis.com/ https://www.gstatic.com; "
        "font-src 'self' data: https://fonts.gstatic.com https://fonts.googleapis.com http://fonts.googleapis.com https://www.gstatic.com;"
        "img-src 'self' data: blob: gs: https://google-ai-skin-tone-research.imgix.net https://storage.cloud.google.com https://storage.googleapis.com https://*.googleusercontent.com https://firebasestorage.googleapis.com https://www.gstatic.com; "
        "media-src 'self' blob: gs: https://deepmind.google https://storage.cloud.google.com https://storage.googleapis.com https://*.googleusercontent.com https://firebasestorage.googleapis.com; "
        "worker-src 'self' blob:;"
    )
    return response


@app.middleware("http")
async def set_request_context(request: Request, call_next):
    user_email = None

    # 1. Try Session Cookie (Firebase Auth)
    session_cookie = request.cookies.get("session_token")
    if session_cookie:
        try:
            decoded_claims = auth.verify_session_cookie(
                session_cookie,
                check_revoked=True,
            )
            user_email = decoded_claims.get("email")
        except Exception:
            # Invalid or expired session cookie
            pass

    # 2. Fallback to IAP or other headers
    if not user_email:
        user_email = request.headers.get("X-Goog-Authenticated-User-Email")

    # 3. Default to anonymous
    is_authenticated = user_email is not None and user_email != "anonymous@google.com"

    if not user_email:
        user_email = "anonymous@google.com"

    if user_email.startswith("accounts.google.com:"):
        user_email = user_email.split(":")[-1]

    user_email = user_email.strip()

    # Inject identity into headers for downstream WSGI (Mesop)
    headers = dict(request.scope["headers"])
    # ASGI headers are lowercase bytes
    headers[b"x-goog-authenticated-user-email"] = user_email.encode("utf-8")
    request.scope["headers"] = [(k, v) for k, v in headers.items()]

    # Redirect unauthenticated users to /welcome for page requests
    path = request.url.path
    accept = request.headers.get("accept", "")

    allowed_paths = ["/welcome", "/forbidden", "/", "/favicon.ico"]
    allowed_prefixes = (
        "/api/",
        "/static/",
        "/__web-components-module__",
        "/media/",
        "/_mesop/",
    )

    # 4. Check Authorization
    is_authorized = is_authenticated and is_user_authorized(user_email)

    if "text/html" in accept:
        if not is_authenticated:
            if path not in allowed_paths and not path.startswith(
                allowed_prefixes,
            ):
                return RedirectResponse(url="/welcome")
        elif not is_authorized:
            if path != "/forbidden" and not path.startswith(allowed_prefixes):
                return RedirectResponse(url="/forbidden")

    session_id = request.cookies.get("session_id")
    if not session_id:
        session_id = str(uuid.uuid4())

    request.scope["MESOP_USER_EMAIL"] = user_email
    request.scope["MESOP_SESSION_ID"] = session_id
    request.scope["MESOP_USER_ROLE"] = (
        get_user_role(user_email) if is_authenticated else "guest"
    )

    # Pass GA ID to Mesop context if it exists
    if config.Default.GA_MEASUREMENT_ID:
        request.scope["MESOP_GA_MEASUREMENT_ID"] = config.Default.GA_MEASUREMENT_ID

    response = await call_next(request)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        samesite="Lax",
    )
    return response


# Test page routes are left as is, they don't need the scaffold
me.page(path="/test_character_consistency", title="Test Character Consistency")(
    test_character_consistency_page,
)
me.page(path="/test_index", title="Test Index")(test_index_page)
me.page(path="/labs", title="Labs: GenMedia Creative Studio")(test_index_page)
me.page(path="/test_infinite_scroll", title="Test Infinite Scroll")(
    test_infinite_scroll_page,
)
me.page(path="/test_pixie_compositor", title="Test Pixie Compositor")(
    test_pixie_compositor_page,
)
me.page(path="/test_uploader", title="Test Uploader")(test_uploader_page)
me.page(path="/test_vto_prompt_generator", title="Test VTO Prompt Generator")(
    test_vto_prompt_generator_page,
)
me.page(path="/test_svg", title="Test SVG")(test_svg_page)
me.page(path="/test_media_chooser", title="Test Media Chooser")(
    test_media_chooser_page,
)
me.page(path="/test_async_veo", title="Test Async Veo")(test_async_veo_page)
me.page(path="/retro_games", title="Retro Games Workflow")(retro_games_page)
me.page(path="/admin", title="Admin Dashboard")(admin_page.page)


# Add a new endpoint to proxy GCS media for better caching.
@app.get("/media/{bucket_name}/{object_path:path}")
async def get_media_proxy(request: Request, bucket_name: str, object_path: str):
    """Securely proxies a GCS object, checking for IAP authentication."""
    user_email = request.scope.get("MESOP_USER_EMAIL")
    app_env = config.Default().APP_ENV

    # Enforce IAP authentication in any environment that is not explicitly a local dev environment.
    development_envs = ["", "dev", "local"]
    if app_env not in development_envs and (
        not user_email or user_email == "anonymous@google.com"
    ):
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(object_path)

        if not blob.exists():
            raise HTTPException(status_code=404, detail="Object not found")

        blob.reload()
        content_type = blob.content_type

        # Set a cache header to instruct browsers and CDNs to cache for 1 hour.
        headers = {"Cache-Control": "public, max-age=3600"}

        # Stream the file content directly from GCS to the user.
        stream = blob.open("rb")
        return StreamingResponse(
            stream,
            media_type=content_type,
            headers=headers,
        )

    except Exception as e:
        print(f"Error proxying GCS object: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/")
def home() -> RedirectResponse:
    return RedirectResponse(url="/welcome")


# Use this to mount the static files for the Mesop app
app.mount(
    "/assets",
    StaticFiles(directory="assets"),
    name="assets",
)
app.mount(
    "/__web-components-module__",
    StaticFiles(directory="."),
    name="web_components",
)
app.mount(
    "/static",
    StaticFiles(
        directory=os.path.join(
            os.path.dirname(inspect.getfile(me)),
            "web",
            "src",
            "app",
            "prod",
            "web_package",
        ),
    ),
    name="static",
)

app.include_router(veo_router.router)


app.mount(
    "/",
    WSGIMiddleware(
        me.create_wsgi_app(
            debug_mode=os.environ.get("DEBUG_MODE", "") == "true",
        ),
    ),
)


if __name__ == "__main__":
    import uvicorn

    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "8080"))

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        reload_includes=["*.py", "*.js"],
        timeout_graceful_shutdown=0,
        proxy_headers=True,
    )
