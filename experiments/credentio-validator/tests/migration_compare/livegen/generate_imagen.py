#!/usr/bin/env python3
"""generate_imagen.py -- generate ONE real Imagen image via Vertex predict.

Replicates the product path ``models/image_models.py`` / Imagen page: a Vertex
``:predict`` against ``.../publishers/google/models/{imagen-model}`` with
``instances=[{"prompt": ...}]`` and ``parameters={"sampleCount": 1, ...}``,
returning ``bytesBase64Encoded`` image. To avoid importing product modules (heavy
deps) this driver issues the SAME predict request over REST -- the same
transport-agnostic pattern the harness already uses.

COST DISCIPLINE: sampleCount=1, ONE image, smallest 1:1 aspect. Generate
exactly once. No retries.

PROBE METHODOLOGY (corrected -- see model-c2pa-inventory.md): an empty-instances
:predict returning 400 does NOT prove the model resolves or is authorized. That
claim was DISPROVEN in WS2: request-body validation runs BEFORE the model-access
check, so an unauthorized/absent model still returns 400 "Empty instances" -- a
FALSE POSITIVE. The DEFINITIVE, no-charge reachability test is the REAL minimal
call itself: a successful 200 means reachable (and bills for the one image); a
404 means no access and is NOT billed. ``free_probe`` below is therefore only a
cheap liveness hint, not an authorization gate -- the real call is authoritative.

Supports the Imagen 4 generate family and the two input-image variants:
  * generate:   --model imagen-4.0-generate-001 (default), -fast, -ultra, preview
  * upscale:    --mode upscale  --input <img>  (imagen-4.0-upscale-preview)
  * recontext:  --mode recontext --input <img> (imagen-product-recontext-preview-06-30)

Usage:
    python generate_imagen.py --model imagen-4.0-generate-001 --out out.png
    python generate_imagen.py --model imagen-4.0-upscale-preview --mode upscale \
        --input seed.png --out up.png
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_PROJECT = "ghchinoy-genai-sa"
DEFAULT_LOCATION = "us-central1"
DEFAULT_PROMPT = "a single red circle on a white background, minimal flat vector"


def _token() -> str:
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True).strip()


def _predict_url(project: str, location: str, model: str) -> str:
    return (f"https://{location}-aiplatform.googleapis.com/v1/projects/{project}"
            f"/locations/{location}/publishers/google/models/{model}:predict")


def _post(url: str, body: dict, token: str) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def free_probe(url: str, token: str) -> bool:
    """Cheap liveness HINT only -- NOT an authorization gate.

    An empty-instances :predict returning 400 does NOT prove the model resolves
    or is authorized (body validation precedes the access check, so an absent /
    unauthorized model also 400s -- a false positive). We therefore never gate
    spend on this result; the caller always proceeds to the real minimal call,
    which is the definitive test (200 = reachable+billed; 404 = no access, NOT
    billed). This probe is retained only as a diagnostic breadcrumb.
    """
    code, body = _post(url, {"instances": []}, token)
    msg = json.dumps(body)[:160]
    print(f"  liveness-hint (empty-instances) [{code}] "
          f"(NON-authoritative; real call is definitive): {msg}")
    return True


def _b64_of(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


def build_body(mode: str, prompt: str, input_img: Path | None) -> dict:
    if mode == "generate":
        return {"instances": [{"prompt": prompt}],
                "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}}
    if mode == "upscale":
        # Imagen upscale: image input + upscaleConfig, sampleCount=1, smallest factor.
        return {
            "instances": [{"prompt": "", "image": {"bytesBase64Encoded": _b64_of(input_img)}}],
            "parameters": {"sampleCount": 1, "mode": "upscale",
                           "upscaleConfig": {"upscaleFactor": "x2"}},
        }
    if mode == "recontext":
        # Product recontext: product image(s) + short prompt, one sample.
        return {
            "instances": [{
                "prompt": prompt,
                "productImages": [{"image": {"bytesBase64Encoded": _b64_of(input_img)}}],
            }],
            "parameters": {"sampleCount": 1},
        }
    raise ValueError(f"unknown mode {mode}")


def generate(model: str, mode: str, prompt: str, input_img: Path | None,
             out: Path, project: str, location: str) -> bool:
    token = _token()
    url = _predict_url(project, location, model)
    # Diagnostic breadcrumb only -- NON-authoritative (see free_probe docstring).
    # The real minimal call below is the definitive reachability test:
    # 200 = reachable (bills one image); 404 = no access (NOT billed).
    free_probe(url, token)
    body = build_body(mode, prompt, input_img)
    print(f"Generating ONE image: model={model}, mode={mode}, sampleCount=1 "
          f"(project={project}, {location})...")
    code, resp = _post(url, body, token)
    preds = resp.get("predictions") if isinstance(resp, dict) else None
    if code != 200 or not preds:
        print(f"  generate failed [{code}]: {json.dumps(resp)[:400]}")
        return False
    b64 = preds[0].get("bytesBase64Encoded") or preds[0].get("image", {}).get("bytesBase64Encoded")
    if not b64:
        print(f"  no image bytes in prediction: {json.dumps(preds[0])[:300]}")
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(b64))
    print(f"Saved image -> {out} ({out.stat().st_size} bytes)")
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--model", default="imagen-4.0-generate-001")
    p.add_argument("--mode", default="generate",
                   choices=["generate", "upscale", "recontext"])
    p.add_argument("--input", help="input image (upscale/recontext modes)")
    p.add_argument("--prompt", default=DEFAULT_PROMPT)
    p.add_argument("--project", default=DEFAULT_PROJECT)
    p.add_argument("--location", default=DEFAULT_LOCATION)
    args = p.parse_args(argv)

    input_img = Path(args.input) if args.input else None
    if args.mode in ("upscale", "recontext") and not (input_img and input_img.exists()):
        print(f"ERROR: --input image required for mode {args.mode}", file=sys.stderr)
        return 2
    ok = generate(args.model, args.mode, args.prompt, input_img,
                  Path(args.out), args.project, args.location)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
