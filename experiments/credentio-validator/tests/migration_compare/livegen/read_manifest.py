#!/usr/bin/env python3
"""read_manifest.py -- C2PA presence detection + FULL manifest dump for one asset.

WS2 model-inventory helper. Where ``compare_real_asset.py`` runs BOTH validators
(credentio + c2pa-python) and diffs on the consumer schema, THIS driver does only
what the WS2 brief requires for a per-model C2PA inventory: presence detection and
capture of the REAL, FULL, UNTRUNCATED manifest JSON via ``c2pa.Reader``.

It deliberately does NOT shell out to the credentio binary (bin/ ships only
PROVENANCE.md in this checkout), so it runs with just c2pa-python installed. The
brief explicitly permits "c2pa.Reader OR the credentio client -- either; this is
presence detection, not a cross-validator comparison."

Output JSON (``--json``):
  {
    "model": ..., "family": ..., "asset": ..., "asset_bytes": N,
    "c2pa": "Yes" | "No",
    "manifest_present": bool,
    "active_manifest": "urn:c2pa:..." | null,
    "absence_detail": "<how absence was confirmed>"  (only when No),
    "manifest_store": { ...FULL c2pa.Reader JSON... }  (only when Yes)
  }

Usage:
    python read_manifest.py --asset a.png --model imagen-4.0-generate-001 \
        --family Imagen --json results_ws2/imagen-4.0-generate-001.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def read_manifest(asset: Path) -> tuple[bool, str, dict | None]:
    """Return (present, detail, full_store). Absence is a normal outcome."""
    import c2pa

    try:
        with c2pa.Reader(str(asset)) as reader:
            store = json.loads(reader.json())
    except Exception as exc:  # noqa: BLE001 - absence surfaces as an exception
        return False, f"c2pa.Reader raised (no readable manifest): {exc}", None
    if not store.get("active_manifest"):
        return False, "c2pa.Reader opened the asset but found no active manifest", store
    return True, f"active_manifest={store.get('active_manifest')!r}", store


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--asset", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--family", default="")
    p.add_argument("--json", metavar="PATH")
    args = p.parse_args(argv)

    asset = Path(args.asset)
    if not asset.exists():
        print(f"ERROR: asset not found: {asset}", file=sys.stderr)
        return 2

    present, detail, store = read_manifest(asset)
    out: dict = {
        "model": args.model,
        "family": args.family,
        "asset": str(asset),
        "asset_bytes": asset.stat().st_size,
        "c2pa": "Yes" if present else "No",
        "manifest_present": present,
        "active_manifest": (store or {}).get("active_manifest") if present else None,
    }
    if present:
        out["manifest_store"] = store
    else:
        out["absence_detail"] = detail

    print(f"{args.model}: C2PA={'Yes' if present else 'No'} ({detail})")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(out, indent=2))
        print(f"  wrote {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
