#!/usr/bin/env python3
"""Phase 1 (GATE) end-to-end demo.

Runs the credentio path (runner -> adapter) on ONE real C2PA-signed JPEG and
prints the normalized, c2pa-python-shaped manifest store. Then reads the SAME
asset with c2pa-python (c2pa.Reader) and compares the two, so the gate criterion
-- "the normalized shape matches c2pa-python's manifest store for that asset" --
is demonstrated, not asserted.

The gate compares the two stores *projected onto the consumer schema* that the
existing call sites actually read (see poc/design.md "The one real mapping
task"): the active manifest id, its claim-generator info (name/version), and its
c2pa.actions actions. Independent-implementation divergences that do NOT change
that consumer schema (credentio exposing extra raw assertions; credentio's
stricter C2PA 2.2 EKU verdict) are reported explicitly as findings, not hidden.

c2pa-python is used here as a DEMO-COMPARE-ONLY dependency; the runner/adapter
core does not import it.

Usage:
    python scripts/demo.py [path/to/asset.jpg]

Exit code 0 iff the consumer-schema projection matches (the gate passes).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_EXP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_EXP_DIR))

from credentio_validator import adapter, runner  # noqa: E402

DEFAULT_ASSET = _EXP_DIR / "testdata" / "signed_v2.jpg"


def _hr(title: str) -> None:
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def _active_manifest(store: dict) -> dict:
    return store.get("manifests", {}).get(store.get("active_manifest"), {})


def _generator_info(manifest: dict) -> list[dict]:
    """Project claim_generator_info to just {name, version} (the fields the
    consumers read); drop implementation-specific extras like the
    org.contentauth.c2pa_rs marker c2pa-python adds."""
    out = []
    for entry in manifest.get("claim_generator_info", []) or []:
        out.append({"name": entry.get("name"), "version": entry.get("version")})
    return out


def _actions(manifest: dict) -> list[dict]:
    """Project the c2pa.actions* assertion to the fields summarize_c2pa reads."""
    out = []
    for a in manifest.get("assertions", []) or []:
        if "c2pa.actions" in a.get("label", ""):
            for act in a.get("data", {}).get("actions", []) or []:
                out.append({
                    "action": act.get("action"),
                    "description": act.get("description"),
                    "digitalSourceType": act.get("digitalSourceType"),
                })
    return out


def consumer_projection(store: dict) -> dict:
    """Project a manifest store onto the schema the existing consumers read."""
    am = _active_manifest(store)
    return {
        "has_active_manifest": bool(store.get("active_manifest")),
        "active_manifest_present_in_map": store.get("active_manifest") in store.get("manifests", {}),
        "generator_info": _generator_info(am),
        "actions": _actions(am),
        "validation_status_is_list": isinstance(store.get("validation_status"), list),
        "validation_status_entry_shape": sorted(
            {k for s in store.get("validation_status", []) or [] for k in s.keys()}
        ),
    }


def _diff(a: dict, b: dict, path: str = "") -> list[str]:
    diffs: list[str] = []
    if type(a) is not type(b):
        return [f"{path or '<root>'}: {type(a).__name__} != {type(b).__name__}"]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                diffs.append(f"{path}.{k}: only in c2pa-python")
            elif k not in b:
                diffs.append(f"{path}.{k}: only in credentio")
            else:
                diffs.extend(_diff(a[k], b[k], f"{path}.{k}"))
    elif isinstance(a, list):
        if a != b:
            diffs.append(f"{path or '<root>'}: {a} != {b}")
    elif a != b:
        diffs.append(f"{path or '<root>'}: {a!r} != {b!r}")
    return diffs


def main() -> int:
    asset = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ASSET
    print(f"Asset under test: {asset}")

    # ---- credentio path: runner -> adapter -----------------------------------
    _hr("1. credentio  (c2pa_validate  ->  runner  ->  adapter)")
    result = runner.run_validate(asset)
    if not result.ok:
        print(f"runner failed (fail-soft): {result.error}")
        if result.stderr:
            print("stderr tail:\n  " + "\n  ".join(result.stderr.splitlines()[-6:]))
        return 2
    if result.stderr.strip():
        print("[c2pa_validate stderr]")
        for line in result.stderr.splitlines():
            print("  " + line)

    credentio_store = adapter.to_manifest_store(result.crjson)
    cred_summary = adapter.summarize(credentio_store)
    print("\nNormalized manifest_store (credentio -> c2pa-python shape):")
    print(json.dumps(credentio_store, indent=2))
    print(f"\ncredentio validation summary: {cred_summary}")

    # ---- reference path: c2pa-python -----------------------------------------
    _hr("2. reference  (c2pa-python  c2pa.Reader)")
    try:
        import c2pa
    except ImportError:
        print("c2pa-python not installed; cannot run the comparison. "
              "Install with `uv sync` / `pip install c2pa-python`.")
        return 3
    with c2pa.Reader(str(asset)) as reader:
        reference_store = json.loads(reader.json())
    print("c2pa-python manifest_store (top-level keys): "
          f"{sorted(reference_store.keys())}")
    ref_summary = adapter.summarize(reference_store)  # same status logic both ways
    print(f"c2pa-python validation summary: {ref_summary}")

    # ---- GATE: compare the consumer-schema projections -----------------------
    _hr("3. GATE: consumer-schema projection  (credentio  vs  c2pa-python)")
    cred_proj = consumer_projection(credentio_store)
    ref_proj = consumer_projection(reference_store)
    print("credentio projection:")
    print(json.dumps(cred_proj, indent=2))
    print("\nc2pa-python projection:")
    print(json.dumps(ref_proj, indent=2))

    diffs = _diff(ref_proj, cred_proj)

    # ---- Documented divergences (reported, NOT gate-failing) -----------------
    _hr("4. Documented divergences (independent-implementation differences)")
    cred_labels = sorted(
        a.get("label") for a in _active_manifest(credentio_store).get("assertions", [])
    )
    ref_labels = sorted(
        a.get("label") for a in _active_manifest(reference_store).get("assertions", [])
    )
    extra = sorted(set(cred_labels) - set(ref_labels))
    print(f"credentio active-manifest assertion labels: {cred_labels}")
    print(f"c2pa-python active-manifest assertion labels: {ref_labels}")
    if extra:
        print(f"- credentio exposes additional RAW assertions c2pa-python "
              f"filters/relocates: {extra}")
    cred_codes = cred_summary["codes"]
    ref_codes = ref_summary["codes"]
    if cred_codes != ref_codes:
        print(f"- validation verdict differs: credentio={cred_codes} "
              f"({cred_summary['status']}) vs c2pa-python={ref_codes} "
              f"({ref_summary['status']}). credentio applies stricter C2PA 2.2 "
              f"cert-profile checks; both are structurally a list of {{code,...}}.")

    # ---- RESULT --------------------------------------------------------------
    _hr("RESULT")
    if not diffs:
        print("GATE PASS: the normalized credentio store matches c2pa-python on "
              "the consumer schema (active manifest, generator info, actions, "
              "validation_status shape) for this asset.")
        return 0
    print("GATE FAIL: consumer-schema projection differs (c2pa-python vs credentio):")
    for d in diffs:
        print("  - " + d)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
