#!/usr/bin/env python3
"""run_migration_compare.py -- run all five surfaces, compare, report.

For each surface (see surfaces.py):
  1. obtain a real signed asset (representative fixture, or live-cheap if given);
  2. validate it with credentio (runner -> adapter, via the spike client core);
  3. validate it with c2pa-python (c2pa.Reader);
  4. project both onto the consumer schema and diff (consumer_schema.py);
  5. print per-surface PASS/FAIL + the actual projections, diffs, and every
     documented expected-divergence.

Exit code 0 iff every surface PASSES (consumed consumer-schema fields match,
modulo documented expected-divergences). Non-zero if any surface FAILS or a
validator could not run.

Run:
    cd experiments/credentio-validator
    # binary must exist at bin/c2pa_validate (copy the spike's pre-built x86_64
    # binary or run scripts/build_credentio.sh) and libc++ runtime must be present
    pip install ".[demo]"          # or: pip install c2pa-python==0.37.7
    python tests/migration_compare/run_migration_compare.py
    # optional JSON report:
    python tests/migration_compare/run_migration_compare.py --json out.json
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

# Make the credentio_validator package importable and locate testdata.
_HERE = Path(__file__).resolve()
_EXP_DIR = _HERE.parent.parent.parent          # experiments/credentio-validator
sys.path.insert(0, str(_EXP_DIR))

from credentio_validator import adapter, runner  # noqa: E402

try:  # works both as ``python -m ...`` and as a direct script invocation
    from . import consumer_schema as cs
    from .surfaces import SURFACES, Surface
except ImportError:  # pragma: no cover - direct-script fallback
    sys.path.insert(0, str(_HERE.parent))
    import consumer_schema as cs  # type: ignore
    from surfaces import SURFACES, Surface  # type: ignore

TESTDATA = _EXP_DIR / "testdata"


def _hr(ch: str = "=") -> str:
    return ch * 78


def _credentio_store(asset: Path) -> dict:
    """Validate with credentio (runner -> adapter). Raises on hard failure."""
    result = runner.run_validate(asset)
    if not result.ok:
        raise RuntimeError(f"credentio failed: {result.error}\n{result.stderr}")
    return adapter.to_manifest_store(result.crjson)


def _c2pa_python_store(asset: Path) -> dict:
    """Validate with c2pa-python (c2pa.Reader), matching the product's call sites."""
    import c2pa

    with c2pa.Reader(str(asset)) as reader:
        return json.loads(reader.json())


def _run_surface(surface: Surface) -> dict:
    asset = TESTDATA / surface.fixture
    print("\n" + _hr())
    print(f"SURFACE: {surface.title}  [{surface.media_type}]")
    print(_hr())
    print(f"  path used          : {surface.path_used}")
    print(f"  asset              : {asset.name}")
    print(f"  generation path    : {surface.generation_path}")
    print(f"  consumption path   : {surface.consumption_path}")
    print(f"  why this path      : {surface.rationale}")
    if surface.special:
        print(f"  LYRIA SPECIAL      : {surface.special}")

    if not asset.exists():
        print(f"  ERROR: asset not found: {asset}")
        return {"surface": surface.key, "status": "ERROR",
                "error": f"asset not found: {asset}"}

    try:
        cred_store = _credentio_store(asset)
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR: credentio validation failed: {exc}")
        return {"surface": surface.key, "status": "ERROR", "error": str(exc)}

    try:
        ref_store = _c2pa_python_store(asset)
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR: c2pa-python validation failed: {exc}")
        return {"surface": surface.key, "status": "ERROR", "error": str(exc)}

    # Comparison is inside the guarded block too: a malformed store must yield a
    # clean ERROR/shape-mismatch, never crash the whole run (review O2).
    try:
        res = cs.compare(ref_store, cred_store)
    except Exception as exc:  # noqa: BLE001
        print(f"  ERROR: comparison failed: {exc}")
        return {"surface": surface.key, "status": "ERROR", "error": str(exc)}

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

    if surface.special:
        # Lyria: highlight the ADDED validation capability explicitly.
        print("\n  LYRIA capability note: today's pass-through path produces NO "
              "validation_status (no validator runs). credentio produces "
              f"{res.cred_codes or '[] (valid)'} -- independent validation the "
              "current Lyria path lacks entirely.")

    print("\n  " + _hr("-"))
    if res.passed:
        print(f"  RESULT: PASS -- consumed consumer-schema fields match "
              f"(modulo {len(res.divergences)} documented expected-divergence(s)).")
    else:
        print("  RESULT: FAIL -- unexplained consumer-schema divergence(s):")
        for d in res.consumer_diffs:
            print(f"    - {d}")

    out = {
        "surface": surface.key,
        "title": surface.title,
        "media_type": surface.media_type,
        "path_used": surface.path_used,
        "asset": asset.name,
        "status": "PASS" if res.passed else "FAIL",
        "ref_projection": res.ref_projection,
        "cred_projection": res.cred_projection,
        "ref_codes": res.ref_codes,
        "cred_codes": res.cred_codes,
        "ref_labels": res.ref_labels,
        "cred_labels": res.cred_labels,
        "consumer_diffs": res.consumer_diffs,
        "divergences": [asdict(d) for d in res.divergences],
        "warnings": res.warnings,
    }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", metavar="PATH", help="write full results as JSON")
    parser.add_argument("--only", metavar="KEY", help="run one surface by key")
    args = parser.parse_args(argv)

    print(_hr())
    print("credentio migration comparison harness -- 5 surfaces, real assets, "
          "both validators, consumer-schema diff")
    print(_hr())

    surfaces = SURFACES
    if args.only:
        surfaces = [s for s in SURFACES if s.key == args.only]
        if not surfaces:
            print(f"no surface with key {args.only!r}", file=sys.stderr)
            return 2

    results = [_run_surface(s) for s in surfaces]

    print("\n" + _hr())
    print("SUMMARY")
    print(_hr())
    n_pass = sum(1 for r in results if r["status"] == "PASS")
    for r in results:
        ndiv = len(r.get("divergences", []))
        print(f"  {r['title']:<14} [{r.get('media_type','?'):<16}] "
              f"{r['status']:<5} ({r.get('path_used','?')}; "
              f"{ndiv} expected-divergence(s))")
    print(f"\n  {n_pass}/{len(results)} surfaces PASS")

    if args.json:
        Path(args.json).write_text(json.dumps(results, indent=2))
        print(f"\n  wrote JSON report: {args.json}")

    all_ok = all(r["status"] == "PASS" for r in results)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
