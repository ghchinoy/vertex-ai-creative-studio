"""Tests for client.py -- transport selection and fail-soft shapes.

Transport-selection and error-shape tests are pure (no binary/network).
The subprocess end-to-end tests are skipped when the credentio binary is absent.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from credentio_validator import client, runner  # noqa: E402

BINARY = runner.DEFAULT_BINARY
TESTDATA = Path(__file__).resolve().parent.parent / "testdata"
_have_binary = BINARY.exists()
needs_binary = pytest.mark.skipif(not _have_binary, reason="credentio binary not built")


# --- transport selection -------------------------------------------------- #

def test_selects_http_when_base_url_passed(monkeypatch):
    calls = {}
    monkeypatch.setattr(client, "_validate_http", lambda url, a: calls.setdefault("http", (url, a)))
    monkeypatch.setattr(client, "_validate_subprocess", lambda a: calls.setdefault("sub", a))
    client.validate("x.jpg", base_url="http://svc:8000")
    assert "http" in calls and "sub" not in calls
    assert calls["http"][0] == "http://svc:8000"


def test_selects_http_when_env_set(monkeypatch):
    calls = {}
    monkeypatch.setenv("CREDENTIO_VALIDATOR_URL", "http://env:9000")
    monkeypatch.setattr(client, "_validate_http", lambda url, a: calls.setdefault("http", url))
    monkeypatch.setattr(client, "_validate_subprocess", lambda a: calls.setdefault("sub", a))
    client.validate("x.jpg")
    assert calls.get("http") == "http://env:9000"


def test_selects_subprocess_when_no_url(monkeypatch):
    calls = {}
    monkeypatch.delenv("CREDENTIO_VALIDATOR_URL", raising=False)
    monkeypatch.setattr(client, "_validate_http", lambda url, a: calls.setdefault("http", url))
    monkeypatch.setattr(client, "_validate_subprocess", lambda a: calls.setdefault("sub", a))
    client.validate("x.jpg")
    assert "sub" in calls and "http" not in calls


def test_explicit_base_url_none_beats_env(monkeypatch):
    # base_url is only overridden by env when the caller didn't pass one.
    monkeypatch.setenv("CREDENTIO_VALIDATOR_URL", "http://env:9000")
    calls = {}
    monkeypatch.setattr(client, "_validate_http", lambda url, a: calls.setdefault("http", url))
    monkeypatch.setattr(client, "_validate_subprocess", lambda a: calls.setdefault("sub", a))
    client.validate("x.jpg", base_url=None)  # None -> fall through to env
    assert calls.get("http") == "http://env:9000"


# --- error shapes --------------------------------------------------------- #

def test_error_summary_shape():
    err = client._error_summary("boom")
    assert err == {"status": "Error", "error_detail": "boom", "actions": [], "generator": "Unknown"}


def test_http_unreachable_is_failsoft(monkeypatch):
    # requests raising -> validate None, summarize Error (never propagates).
    def boom(*a, **k):
        raise OSError("connection refused")
    import requests
    monkeypatch.setattr(requests, "post", boom)
    assert client.validate("x.jpg", base_url="http://nope:1") is None
    assert client.summarize("x.jpg", base_url="http://nope:1")["status"] == "Error"


# --- subprocess end-to-end (needs binary) --------------------------------- #

@needs_binary
def test_subprocess_validate_returns_store_for_signed_asset():
    store = client.validate(str(TESTDATA / "signed_v2.jpg"))
    assert store is not None
    assert "active_manifest" in store and "manifests" in store


@needs_binary
def test_subprocess_validate_none_for_no_manifest(tmp_path):
    from PIL import Image
    p = tmp_path / "plain.jpg"
    Image.new("RGB", (32, 32), "green").save(p)
    assert client.validate(str(p)) is None


@needs_binary
def test_subprocess_summarize_error_for_no_manifest(tmp_path):
    from PIL import Image
    p = tmp_path / "plain.jpg"
    Image.new("RGB", (32, 32), "green").save(p)
    assert client.summarize(str(p))["status"] == "Error"


@needs_binary
def test_subprocess_summarize_untrusted_label():
    summary = client.summarize(str(TESTDATA / "untrusted_sandbox.jpg"))
    assert summary["status"] == "Untrusted (Sandbox)"
