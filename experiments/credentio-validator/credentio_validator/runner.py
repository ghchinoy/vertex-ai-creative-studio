"""runner.py -- subprocess invocation of the credentio ``c2pa_validate`` CLI.

This is the spike's validation *engine*: it shells out to the credentio C++
binary with an asset and (optionally) trust anchors, and returns the binary's
native crJSON output parsed into a dict.

Fail-soft parity (required even in Phase 1): a missing binary, a non-zero exit,
or a timeout must NOT raise into the caller -- they are returned as a structured
result with ``ok=False`` and an ``error`` message. The caller (demo now; the
client/service later) decides how to surface that.

CLI contract (pinned from the credentio source, tools/asset_validator_main.cc):
    c2pa_validate --asset=<path>
                  [--claim_signer_trust=<pem>]   # claim signer trust anchors
                  [--tsa_trust=<pem>]             # timestamp-authority anchors
                  [--output_format=crjson|txtpb]  # default: crjson

Output shape on success (stdout), crjson mode:
    Validation successful!
    Validation Result (crjson):
    { ...crJSON... }
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# Repository-relative defaults. bin/c2pa_validate is produced by
# scripts/build_credentio.sh; the bundled conformance anchors live in trust/.
_PKG_DIR = Path(__file__).resolve().parent
_EXP_DIR = _PKG_DIR.parent
DEFAULT_BINARY = _EXP_DIR / "bin" / "c2pa_validate"
DEFAULT_CLAIM_SIGNER_TRUST = _EXP_DIR / "trust" / "c2pa_conformance_anchors.pem"

DEFAULT_TIMEOUT_S = 60

# The credentio binary exposes NO --version flag (absl prints only the program
# name). credentio's MODULE.bazel declares module c2pa version 0.1.0; the spike
# built commit 4ac69fc. We report that here for /healthz -- honest and pinned,
# since the binary itself carries no queryable version.
CREDENTIO_VERSION = "0.1.0 (c2pa module; built from commit 4ac69fc; no --version flag)"


def binary_info(binary: str | os.PathLike | None = None) -> dict:
    """Best-effort health/version info for the credentio binary (for /healthz)."""
    bin_path = _resolve_binary(binary)
    return {
        "available": Path(bin_path).exists(),
        "path": str(bin_path),
        "credentio_version": CREDENTIO_VERSION,
    }


@dataclass
class RunnerResult:
    """Structured, fail-soft result of one c2pa_validate invocation."""

    ok: bool
    crjson: dict | None = None          # parsed credentio crJSON, if any
    returncode: int | None = None
    stdout: str = ""
    stderr: str = ""
    error: str | None = None            # populated on any failure
    no_manifest: bool = False           # True when the asset simply has no C2PA
                                        # manifest -- a RESULT, not a fault
                                        # (see design POST /validate contract)
    cmd: list[str] = field(default_factory=list)


# credentio prints this to stderr (exit 1) when an asset carries no C2PA
# manifest. That is a normal result (like c2pa-python's ManifestNotFound), NOT a
# service fault -- callers/the service must not surface it as a 5xx.
_NO_MANIFEST_MARKER = "No manifest store found"


def _resolve_binary(binary: str | os.PathLike | None) -> Path:
    if binary is not None:
        return Path(binary)
    env = os.environ.get("CREDENTIO_VALIDATE_BIN")
    if env:
        return Path(env)
    return DEFAULT_BINARY


def _extract_crjson(stdout: str) -> dict | None:
    """Pull the crJSON object out of the CLI's stdout.

    The binary prefixes the JSON with human-readable header lines
    ("Validation successful!" / "Validation Result (crjson):"), so we cannot
    ``json.loads`` the whole stream -- we slice from the first ``{`` and parse.
    """
    marker = "Validation Result (crjson):"
    idx = stdout.find(marker)
    start = stdout.find("{", idx if idx != -1 else 0)
    if start == -1:
        return None
    try:
        # object_hook-free; the CLI emits a single top-level JSON object then a
        # trailing newline, so decoding from `start` to the end is safe.
        return json.loads(stdout[start:])
    except json.JSONDecodeError:
        # Be forgiving of any trailing text after the object.
        decoder = json.JSONDecoder()
        try:
            obj, _ = decoder.raw_decode(stdout[start:])
            return obj
        except json.JSONDecodeError:
            return None


def run_validate(
    asset_path: str | os.PathLike,
    *,
    claim_signer_trust: str | os.PathLike | None = DEFAULT_CLAIM_SIGNER_TRUST,
    tsa_trust: str | os.PathLike | None = None,
    binary: str | os.PathLike | None = None,
    timeout: int = DEFAULT_TIMEOUT_S,
) -> RunnerResult:
    """Invoke ``c2pa_validate`` on one asset and return its parsed crJSON.

    Never raises for asset-level or process-level failures; those become a
    ``RunnerResult`` with ``ok=False`` and an ``error`` string.
    """
    bin_path = _resolve_binary(binary)
    if not Path(bin_path).exists():
        return RunnerResult(
            ok=False,
            error=(
                f"credentio binary not found at {bin_path}. Build it with "
                "scripts/build_credentio.sh or set CREDENTIO_VALIDATE_BIN."
            ),
        )

    asset = Path(asset_path)
    if not asset.exists():
        return RunnerResult(ok=False, error=f"asset not found: {asset}")

    cmd: list[str] = [str(bin_path), f"--asset={asset}", "--output_format=crjson"]
    if claim_signer_trust:
        cmd.append(f"--claim_signer_trust={claim_signer_trust}")
    if tsa_trust:
        cmd.append(f"--tsa_trust={tsa_trust}")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return RunnerResult(ok=False, error=f"c2pa_validate timed out after {timeout}s", cmd=cmd)
    except OSError as exc:  # e.g. not executable
        return RunnerResult(ok=False, error=f"failed to exec c2pa_validate: {exc}", cmd=cmd)

    if proc.returncode != 0:
        # Distinguish "no manifest" (a normal result) from a genuine fault.
        if _NO_MANIFEST_MARKER in proc.stderr:
            return RunnerResult(
                ok=False,
                no_manifest=True,
                returncode=proc.returncode,
                stdout=proc.stdout,
                stderr=proc.stderr,
                error="no C2PA manifest found",
                cmd=cmd,
            )
        return RunnerResult(
            ok=False,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            error=f"c2pa_validate exited {proc.returncode}",
            cmd=cmd,
        )

    crjson = _extract_crjson(proc.stdout)
    if crjson is None:
        return RunnerResult(
            ok=False,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            error="could not parse crJSON from c2pa_validate stdout",
            cmd=cmd,
        )

    return RunnerResult(
        ok=True,
        crjson=crjson,
        returncode=proc.returncode,
        stdout=proc.stdout,
        stderr=proc.stderr,
        cmd=cmd,
    )
