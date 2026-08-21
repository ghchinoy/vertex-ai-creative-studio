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


# --- no-manifest sentinel: pin the coupling so message drift breaks a test ---
# (review cleanup item 1). _NO_MANIFEST_MARKER is the ONLY thing separating a
# 200 no-manifest result from a 5xx fault; if a future credentio build changes
# the stderr phrase these tests fail loudly instead of the contract regressing
# silently.

def test_no_manifest_marker_is_pinned():
    # The exact literal we rely on from credentio's stderr.
    assert runner._NO_MANIFEST_MARKER == "No manifest store found"


def test_no_manifest_marker_yields_no_manifest_flag(tmp_path):
    # A binary that exits 1 with the marker on stderr must be classified as
    # no_manifest (a result), not a generic fault.
    asset = tmp_path / "a.jpg"
    asset.write_bytes(b"x")
    fake = tmp_path / "fake_validate.sh"
    fake.write_text(
        "#!/bin/sh\n"
        'echo "NOT_FOUND: No manifest store found" 1>&2\n'
        "exit 1\n"
    )
    fake.chmod(0o755)
    r = runner.run_validate(asset, binary=str(fake), claim_signer_trust=None)
    assert r.ok is False
    assert r.no_manifest is True
    assert r.returncode == 1


def test_other_nonzero_exit_is_not_no_manifest(tmp_path):
    # A different stderr (no marker) must NOT be classified as no_manifest.
    asset = tmp_path / "a.jpg"
    asset.write_bytes(b"x")
    fake = tmp_path / "fake_validate.sh"
    fake.write_text("#!/bin/sh\necho 'some other error' 1>&2\nexit 2\n")
    fake.chmod(0o755)
    r = runner.run_validate(asset, binary=str(fake), claim_signer_trust=None)
    assert r.ok is False
    assert r.no_manifest is False
