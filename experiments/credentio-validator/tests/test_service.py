"""Tests for service.py -- the FastAPI wrapper.

The no-manifest-vs-fault distinction (review item 1) is tested by monkeypatching
runner.run_validate, so these run without the binary. A couple of end-to-end
tests against the real binary are skipped when it is absent.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from credentio_validator import runner, service  # noqa: E402
from credentio_validator.runner import RunnerResult  # noqa: E402

client = TestClient(service.app, raise_server_exceptions=False)

BINARY = runner.DEFAULT_BINARY
TESTDATA = Path(__file__).resolve().parent.parent / "testdata"
needs_binary = pytest.mark.skipif(not BINARY.exists(), reason="credentio binary not built")


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"ok", "credentio_version"}


def test_no_manifest_is_200_not_5xx(monkeypatch, tmp_path):
    # A well-formed request for an asset with no manifest is a RESULT.
    asset = tmp_path / "a.jpg"
    asset.write_bytes(b"not really a jpeg")
    monkeypatch.setattr(
        runner, "run_validate",
        lambda *a, **k: RunnerResult(ok=False, no_manifest=True, error="no C2PA manifest found"),
    )
    r = client.post("/validate", json={"asset_uri": str(asset)})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["manifest_store"] is None
    assert body["validation"]["status"] == "none"


def test_genuine_fault_is_5xx(monkeypatch, tmp_path):
    asset = tmp_path / "a.jpg"
    asset.write_bytes(b"data")
    monkeypatch.setattr(
        runner, "run_validate",
        lambda *a, **k: RunnerResult(ok=False, error="c2pa_validate exited 2"),
    )
    r = client.post("/validate", json={"asset_uri": str(asset)})
    assert r.status_code == 500
    body = r.json()
    assert body["ok"] is False
    assert body["error"] == "c2pa_validate exited 2"


def test_unsupported_scheme_is_fault():
    r = client.post("/validate", json={"asset_uri": "gs://bucket/obj.jpg"})
    assert r.status_code == 501
    assert r.json()["ok"] is False


@needs_binary
def test_validate_signed_asset_end_to_end():
    r = client.post("/validate", json={"asset_uri": str(TESTDATA / "signed_v2.jpg"), "summarize": True})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["manifest_store"]["active_manifest"]
    assert body["summary"]["status"].startswith(("Valid", "Invalid", "Untrusted"))


@needs_binary
def test_validate_untrusted_end_to_end():
    r = client.post("/validate", json={"asset_uri": str(TESTDATA / "untrusted_sandbox.jpg"), "summarize": True})
    assert r.status_code == 200
    body = r.json()
    assert body["validation"]["status"] == "untrusted"
    assert body["summary"]["status"] == "Untrusted (Sandbox)"


@needs_binary
@pytest.mark.parametrize("fixture", ["signed_video.mp4", "signed_audio.m4a"])
def test_validate_video_audio_end_to_end(fixture):
    path = TESTDATA / fixture
    if not path.exists():
        pytest.skip(f"{fixture} fixture not generated")
    r = client.post("/validate", json={"asset_uri": str(path)})
    assert r.status_code == 200
    assert r.json()["ok"] is True
    assert r.json()["manifest_store"]["active_manifest"]
