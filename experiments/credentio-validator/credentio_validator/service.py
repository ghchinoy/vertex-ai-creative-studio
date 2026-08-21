"""service.py -- FastAPI HTTP wrapper around the credentio validator.

Phase 2 of the spike. Reuses the EXACT Phase 1 runner + adapter as its engine;
adds no new validation logic. Endpoints (see poc/design.md):

    POST /validate  -> ValidateResponse
    GET  /healthz   -> HealthResponse

Fail-soft contract:
  * A well-formed request for an asset with NO manifest is a RESULT
    (HTTP 200, ok=true, manifest_store=null) -- NOT a 5xx. (Resolves review
    item 1: runner now flags no_manifest so the service can distinguish it from
    a genuine fault.)
  * HTTP 5xx is reserved for genuine service faults (binary missing/crash,
    timeout, unparseable output). The body still follows ValidateResponse so the
    client wrapper maps it to a sentinel.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from . import adapter, runner
from .schema import HealthResponse, ValidateRequest, ValidateResponse, ValidationBlock

app = FastAPI(
    title="credentio C2PA validator (spike)",
    version="0.1.0",
    description="Standalone read/validate-only C2PA validator over the credentio CLI.",
)


def _resolve_to_local(asset_uri: str) -> tuple[str, bool]:
    """Return (local_path, is_temp). Downloads http(s):// to a temp file.

    Mirrors C2PAService.read_manifest's download-to-temp pattern. gs:// is not
    wired in the spike service (it needs GCS credentials); a clear error is
    raised so it surfaces as a fault, not a silent wrong answer.
    """
    parsed = urlparse(asset_uri)
    scheme = parsed.scheme.lower()

    if scheme in ("", "file"):
        return (parsed.path if scheme == "file" else asset_uri), False

    if scheme in ("http", "https"):
        import requests  # local import; demo/service-only dependency

        suffix = os.path.splitext(parsed.path)[1] or ".bin"
        fd, local_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        resp = requests.get(asset_uri, timeout=30)
        resp.raise_for_status()
        with open(local_path, "wb") as f:
            f.write(resp.content)
        return local_path, True

    if scheme == "gs":
        raise NotImplementedError(
            "gs:// is not wired in the spike service (needs GCS credentials); "
            "download the asset and POST a local path or http(s) URL."
        )

    raise ValueError(f"unsupported asset_uri scheme: {scheme!r}")


@app.get("/healthz", response_model=HealthResponse)
def healthz() -> HealthResponse:
    info = runner.binary_info()
    return HealthResponse(ok=bool(info["available"]),
                          credentio_version=info["credentio_version"])


@app.post("/validate", response_model=ValidateResponse)
def validate(req: ValidateRequest) -> JSONResponse:
    local_path = None
    is_temp = False
    try:
        try:
            local_path, is_temp = _resolve_to_local(req.asset_uri)
        except NotImplementedError as exc:
            return _fault(str(exc), status=501)
        except Exception as exc:  # download / bad URI => service fault
            return _fault(f"could not resolve asset_uri: {exc}", status=502)

        result = runner.run_validate(local_path)

        # No manifest is a RESULT, not a fault (HTTP 200).
        if result.no_manifest:
            return _ok(ValidateResponse(
                ok=True, manifest_store=None,
                validation=ValidationBlock(status="none", codes=[]),
                summary=None, raw=None, error=None,
            ))

        # Genuine service fault (binary missing, timeout, crash, unparseable).
        if not result.ok:
            return _fault(result.error or "validation failed", status=500)

        store = adapter.to_manifest_store(result.crjson)
        verdict = adapter.summarize(store)
        summary = adapter.build_summary(store) if req.summarize else None
        return _ok(ValidateResponse(
            ok=True,
            manifest_store=store,
            validation=ValidationBlock(status=verdict["status"], codes=verdict["codes"]),
            summary=summary,
            raw=result.crjson,
            error=None,
        ))
    finally:
        if is_temp and local_path and os.path.exists(local_path):
            try:
                os.remove(local_path)
            except OSError:
                pass


def _ok(resp: ValidateResponse) -> JSONResponse:
    return JSONResponse(status_code=200, content=resp.model_dump())


def _fault(message: str, *, status: int) -> JSONResponse:
    """A genuine service fault: 5xx, but the body still follows ValidateResponse."""
    return JSONResponse(
        status_code=status,
        content=ValidateResponse(
            ok=False, manifest_store=None, validation=None,
            summary=None, raw=None, error=message,
        ).model_dump(),
    )
