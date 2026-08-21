"""client.py -- the drop-in surface all call sites use (Phase 3).

Two transports, one shape:
  * HTTP transport      -- when base_url or $CREDENTIO_VALIDATOR_URL is set,
                           POSTs to the Phase 2 service's /validate.
  * subprocess transport -- otherwise, runs runner+adapter in-process.

Both transports return IDENTICAL shapes, so migrating a real call site is a
config flag, never a call-site change:

  validate(asset_uri) -> dict | None
      Drop-in for services/c2pa_service.py::C2PAService.read_manifest and for
      experiments/veo-variations/core/c2pa.py::get_c2pa_manifest's happy path.
      Returns the c2pa-python-shaped manifest_store dict, or None if there is no
      manifest OR any failure (matches read_manifest's ManifestNotFound/error->None).

  summarize(asset_uri) -> dict
      Drop-in for veo-variations summarize_c2pa. Returns
      {"status","generator","actions":[...]} on success with status labels
      "Valid" | "Untrusted (Sandbox)" | "Invalid (<code>)", or
      {"status":"Error","error_detail":...,"actions":[],"generator":"Unknown"}
      on any failure. (Resolves review item 3.)

Fail-soft everywhere: no transport error, HTTP 5xx, or timeout is ever raised
into the caller -- it becomes None / the Error dict.
"""

from __future__ import annotations

import os

from . import adapter, runner

ENV_URL = "CREDENTIO_VALIDATOR_URL"


def _error_summary(detail: str) -> dict:
    """The exact summarize_c2pa failure-path dict."""
    return {
        "status": "Error",
        "error_detail": detail,
        "actions": [],
        "generator": "Unknown",
    }


def _pick_base_url(base_url: str | None) -> str | None:
    return base_url if base_url is not None else os.environ.get(ENV_URL) or None


# --------------------------------------------------------------------------- #
# subprocess transport
# --------------------------------------------------------------------------- #
def _validate_subprocess(asset_uri: str) -> dict | None:
    result = runner.run_validate(asset_uri)
    if result.no_manifest or not result.ok:
        return None
    return adapter.to_manifest_store(result.crjson)


def _summarize_subprocess(asset_uri: str) -> dict:
    result = runner.run_validate(asset_uri)
    if result.no_manifest:
        return _error_summary("No C2PA manifest found in this file.")
    if not result.ok:
        return _error_summary(result.error or "validation failed")
    store = adapter.to_manifest_store(result.crjson)
    return adapter.build_summary(store)


# --------------------------------------------------------------------------- #
# HTTP transport
# --------------------------------------------------------------------------- #
def _post_validate(base_url: str, asset_uri: str, *, summarize: bool) -> dict | None:
    """POST /validate; return the parsed JSON body, or None on a true transport
    fault (connection refused, timeout, non-JSON body). Fail-soft -- never raises.

    Note we parse the body regardless of HTTP status: the service returns a
    structured ValidateResponse body even for a 5xx fault (ok=false, error=...),
    and both callers key their verdict off ``body["ok"]``, not the HTTP status.
    Parsing it lets the HTTP transport carry the same ``error`` string the
    subprocess transport sees -- keeping the two transports' shapes identical.
    """
    import requests

    url = base_url.rstrip("/") + "/validate"
    try:
        resp = requests.post(
            url,
            json={"asset_uri": asset_uri, "summarize": summarize},
            timeout=90,
        )
    except Exception:
        return None
    try:
        return resp.json()
    except ValueError:
        return None


def _validate_http(base_url: str, asset_uri: str) -> dict | None:
    body = _post_validate(base_url, asset_uri, summarize=False)
    if not body or not body.get("ok"):
        return None
    return body.get("manifest_store")  # None when no manifest -> matches read_manifest


def _summarize_http(base_url: str, asset_uri: str) -> dict:
    body = _post_validate(base_url, asset_uri, summarize=True)
    if not body:
        return _error_summary("validator service unreachable or faulted")
    if not body.get("ok"):
        return _error_summary(body.get("error") or "validation failed")
    if body.get("manifest_store") is None:
        return _error_summary("No C2PA manifest found in this file.")
    summary = body.get("summary")
    if summary is None:
        # Service didn't include a summary; derive it locally from the store so
        # both transports still return identical shapes.
        return adapter.build_summary(body["manifest_store"])
    return summary


# --------------------------------------------------------------------------- #
# public surface
# --------------------------------------------------------------------------- #
def validate(asset_uri: str, *, base_url: str | None = None) -> dict | None:
    """Return the manifest_store dict, or None (no manifest / any failure)."""
    url = _pick_base_url(base_url)
    if url:
        return _validate_http(url, asset_uri)
    return _validate_subprocess(asset_uri)


def summarize(asset_uri: str, *, base_url: str | None = None) -> dict:
    """Return the summarize_c2pa-shaped dict (success or Error)."""
    url = _pick_base_url(base_url)
    if url:
        return _summarize_http(url, asset_uri)
    return _summarize_subprocess(asset_uri)
