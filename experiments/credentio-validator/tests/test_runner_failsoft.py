"""Fail-soft tests for runner.py.

The runner must never raise into the caller for asset- or process-level
failures; it returns a RunnerResult(ok=False, error=...). These tests need no
binary (they exercise the missing-asset and missing-binary paths).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from credentio_validator import runner  # noqa: E402


def test_missing_asset_is_failsoft():
    r = runner.run_validate("/no/such/asset.jpg", binary="/bin/true")
    assert r.ok is False
    assert "asset not found" in (r.error or "")


def test_missing_binary_is_failsoft(tmp_path):
    asset = tmp_path / "a.jpg"
    asset.write_bytes(b"not a real jpeg")
    r = runner.run_validate(asset, binary="/definitely/not/here")
    assert r.ok is False
    assert "not found" in (r.error or "")


def test_nonzero_exit_is_failsoft(tmp_path):
    # /bin/false exits 1 -> must be caught, not raised.
    asset = tmp_path / "a.jpg"
    asset.write_bytes(b"x")
    r = runner.run_validate(asset, binary="/bin/false", claim_signer_trust=None)
    assert r.ok is False
    assert r.returncode == 1


def test_unparseable_output_is_failsoft(tmp_path):
    # /bin/true exits 0 but prints nothing -> crjson parse fails -> fail-soft.
    asset = tmp_path / "a.jpg"
    asset.write_bytes(b"x")
    r = runner.run_validate(asset, binary="/bin/true", claim_signer_trust=None)
    assert r.ok is False
    assert "could not parse" in (r.error or "")
