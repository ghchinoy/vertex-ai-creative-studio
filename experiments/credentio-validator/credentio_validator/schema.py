"""schema.py -- pydantic request/response models for the validator service.

Mirrors the interface contract in poc/design.md (POST /validate, GET /healthz).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ValidateRequest(BaseModel):
    """POST /validate request body."""

    asset_uri: str = Field(
        ...,
        description="Local path, http(s):// URL, or gs:// URI of the asset to validate.",
    )
    summarize: bool = Field(
        default=False,
        description="When true, also return the summarize_c2pa-shaped `summary` block.",
    )


class ValidationBlock(BaseModel):
    """Design-vocabulary validation verdict: valid | untrusted | invalid."""

    status: str
    codes: list[str] = Field(default_factory=list)


class ValidateResponse(BaseModel):
    """POST /validate response body (fail-soft; see design contract).

    A well-formed request always yields HTTP 200 with a structured body; an asset
    that simply has no manifest is a *result* (`manifest_store: null`), not an
    error. HTTP 5xx is reserved for genuine service faults (binary missing/crash),
    and even then the body follows this shape so the client can map it to a
    sentinel.
    """

    ok: bool
    manifest_store: dict | None = None
    validation: ValidationBlock | None = None
    summary: dict | None = None
    raw: dict | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """GET /healthz response body."""

    ok: bool
    credentio_version: str
