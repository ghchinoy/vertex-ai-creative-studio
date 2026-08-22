#!/usr/bin/env python3
"""compare_real_asset.py -- run BOTH validators on a REAL generated asset and
diff on the consumer schema, reusing the migration_compare harness UNCHANGED.

This is the live-generation counterpart to
``tests/migration_compare/run_migration_compare.py``. That runner is
fixture-driven (it reads ``surfaces.py`` fixtures under ``testdata/``); this
driver points the *same* comparison machinery at an arbitrary real asset path
produced by the live-generation scripts in this directory.

It does three things for one asset:
  1. Report whether the asset carries a C2PA manifest AT ALL. Many Google
     outputs carry SynthID but may NOT embed a C2PA manifest -- if so, that is a
     KEY FINDING and there is no validator diff to run.
  2. If a manifest is present: validate with credentio (runner -> adapter) and
     with c2pa-python (c2pa.Reader), project both onto the consumer schema, and
     diff using the harness's EXISTING pass/fail rule (consumer_schema.compare).
  3. Emit a machine-readable JSON result (``--json``) for the write-up.

No product C2PA code is imported or modified. This is a test/analysis driver.

Usage:
    cd experiments/credentio-validator
    python tests/migration_compare/livegen/compare_real_asset.py \
        --asset path/to/real_asset.png --title "Gemini Image" [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Locate experiments/credentio-validator so the spike client + harness import.
_HERE = Path(__file__).resolve()
_MIGRATION_DIR = _HERE.parent.parent          # tests/migration_compare
_EXP_DIR = _MIGRATION_DIR.parent.parent       # experiments/credentio-validator
sys.path.insert(0, str(_EXP_DIR))
sys.path.insert(0, str(_MIGRATION_DIR))

from credentio_validator import adapter, runner  # noqa: E402
import consumer_schema as cs                     # noqa: E402


def _hr(ch: str = "=") -> str:
    return ch * 78


def has_c2pa_manifest(asset: Path) -> tuple[bool, str]:
    """Return (present, detail). present is True iff c2pa-python can read an
    active manifest from the asset. A missing/absent manifest is a normal,
    reportable outcome, not an error."""
    import c2pa

    try:
        with c2pa.Reader(str(asset)) as reader:
            store = json.loads(reader.json())
    except Exception as exc:  # noqa: BLE001 - absence surfaces as an exception
        return False, f"c2pa.Reader could not read a manifest: {exc}"
    if not store.get("active_manifest"):
        return False, "c2pa.Reader opened the asset but found no active manifest"
    return True, f"active_manifest={store.get('active_manifest')!r}"


def _credentio_store(asset: Path) -> dict:
    result = runner.run_validate(asset)
    if not result.ok:
        raise RuntimeError(f"credentio failed: {result.error}\n{result.stderr}")
    return adapter.to_manifest_store(result.crjson)


def _c2pa_python_store(asset: Path) -> dict:
    import c2pa

    with c2pa.Reader(str(asset)) as reader:
        return json.loads(reader.json())


def compare_asset(asset: Path, title: str) -> dict:
    print("\n" + _hr())
    print(f"REAL ASSET SURFACE: {title}")
    print(_hr())
    print(f"  asset : {asset}")
    print(f"  size  : {asset.stat().st_size} bytes" if asset.exists() else "  MISSING")

    if not asset.exists():
        return {"title": title, "asset": str(asset), "status": "ERROR",
                "error": "asset not found", "manifest_present": False}

    present, detail = has_c2pa_manifest(asset)
    print(f"\n  C2PA manifest present? {present}  ({detail})")

    out: dict = {
        "title": title,
        "asset": str(asset),
        "asset_bytes": asset.stat().st_size,
        "manifest_present": present,
        "manifest_detail": detail,
    }

    if not present:
        # KEY FINDING: real output carries no C2PA manifest. No diff possible.
        print("\n  FINDING: asset carries NO C2PA manifest -- no validator diff "
              "possible for this surface. (Google outputs may carry SynthID "
              "watermarking without an embedded C2PA manifest.)")
        out["status"] = "NO_MANIFEST"
        return out

    try:
        cred_store = _credentio_store(asset)
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR: credentio validation failed: {exc}")
        out["status"] = "ERROR"
        out["error"] = f"credentio: {exc}"
        return out

    try:
        ref_store = _c2pa_python_store(asset)
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR: c2pa-python validation failed: {exc}")
        out["status"] = "ERROR"
        out["error"] = f"c2pa-python: {exc}"
        return out

    res = cs.compare(ref_store, cred_store)

    print("\n  consumer-schema projection -- c2pa-python (incumbent):")
    print("    " + json.dumps(res.ref_projection, indent=2).replace("\n", "\n    "))
    print("\n  consumer-schema projection -- credentio (candidate):")
    print("    " + json.dumps(res.cred_projection, indent=2).replace("\n", "\n    "))
    print("\n  raw validation_status codes:")
    print(f"    c2pa-python: {res.ref_codes}")
    print(f"    credentio  : {res.cred_codes}")

    if res.divergences:
        print("\n  documented expected-divergences (reported, NOT failures):")
        for d in res.divergences:
            print(f"    [{d.code} {d.title}] {d.detail}")
    else:
        print("\n  documented expected-divergences: none")

    if res.warnings:
        print("\n  warnings (non-failing signals):")
        for w in res.warnings:
            print(f"    [!] {w}")

    print("\n  " + _hr("-"))
    if res.passed:
        print(f"  RESULT: PASS -- consumed consumer-schema fields match "
              f"(modulo {len(res.divergences)} documented expected-divergence(s)).")
    else:
        print("  RESULT: FAIL -- unexplained consumer-schema divergence(s):")
        for d in res.consumer_diffs:
            print(f"    - {d}")

    out.update({
        "status": "PASS" if res.passed else "FAIL",
        "ref_projection": res.ref_projection,
        "cred_projection": res.cred_projection,
        "ref_codes": res.ref_codes,
        "cred_codes": res.cred_codes,
        "ref_labels": res.ref_labels,
        "cred_labels": res.cred_labels,
        "consumer_diffs": res.consumer_diffs,
        "divergences": [d.__dict__ for d in res.divergences],
        "warnings": res.warnings,
    })
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset", required=True, help="path to a real generated asset")
    p.add_argument("--title", required=True, help="surface title, e.g. 'Gemini Image'")
    p.add_argument("--json", metavar="PATH", help="write the result as JSON")
    args = p.parse_args(argv)

    result = compare_asset(Path(args.asset), args.title)
    if args.json:
        Path(args.json).write_text(json.dumps(result, indent=2))
        print(f"\n  wrote JSON: {args.json}")

    # Exit 0 for a successful PASS or a documented NO_MANIFEST finding (both are
    # valid results); non-zero only for a real FAIL or a hard ERROR.
    return 0 if result.get("status") in ("PASS", "NO_MANIFEST") else 1


if __name__ == "__main__":
    raise SystemExit(main())
