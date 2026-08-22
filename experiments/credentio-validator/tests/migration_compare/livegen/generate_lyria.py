#!/usr/bin/env python3
"""generate_lyria.py -- generate ONE real Lyria music sample.

Replicates the product path ``models/lyria.py::generate_music_with_lyria`` for
``lyria-002``: a Vertex ``PredictionServiceClient.predict`` against
``.../publishers/google/models/lyria-002`` with ``instances=[{"prompt": ...}]``
and ``parameters={"sampleCount": 1}``, returning ``bytesBase64Encoded`` WAV. To
avoid importing the product module (heavy deps) this driver issues the SAME
predict request over REST -- the request body mirrors the product call exactly.

COST DISCIPLINE: sampleCount=1, ONE sample. FREE-probe (predict with empty
instances -> 400 iff the model resolves and is authorized) runs first.

Usage:
    python tests/migration_compare/livegen/generate_lyria.py \
        --out tests/migration_compare/livegen/assets/lyria.wav
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

DEFAULT_MODEL = "lyria-002"
DEFAULT_LOCATION = "us-central1"   # matches cfg.LYRIA_LOCATION default
DEFAULT_PROMPT = "a short calm solo piano melody"
DEFAULT_PROJECT = "ghchinoy-genai-sa"


def _token() -> str:
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True).strip()


def _predict_url(project: str, location: str, model: str) -> str:
    # The product uses the regional API endpoint with the global publisher path;
    # both resolve (verified by free-probe). Use the regional host directly.
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
    """FREE probe: empty instances -> 400 INVALID_ARGUMENT iff resolved+authorized
    (no generation, no cost). 404/403 means unavailable/unauthorized."""
    code, body = _post(url, {"instances": []}, token)
    msg = json.dumps(body)[:160]
    if code == 400:
        print(f"  FREE-probe [{code}] resolves+authorized (empty-instances 400): {msg}")
        return True
    print(f"  FREE-probe [{code}] UNAVAILABLE/UNAUTHORIZED: {msg}")
    return False


def generate(url: str, prompt: str, out: Path, token: str) -> bool:
    body = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1}}
    print(f"Generating ONE Lyria sample (sampleCount=1)...")
    code, resp = _post(url, body, token)
    preds = resp.get("predictions") if isinstance(resp, dict) else None
    if code != 200 or not preds or not preds[0].get("bytesBase64Encoded"):
        print(f"  generate failed [{code}]: {json.dumps(resp)[:300]}")
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(preds[0]["bytesBase64Encoded"]))
    print(f"Saved WAV -> {out} ({out.stat().st_size} bytes)")
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--project", default=DEFAULT_PROJECT)
    p.add_argument("--location", default=DEFAULT_LOCATION)
    p.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = p.parse_args(argv)

    token = _token()
    url = _predict_url(args.project, args.location, args.model)
    if not free_probe(url, token):
        print("FREE-probe failed; not spending.", file=sys.stderr)
        return 1
    ok = generate(url, args.prompt, Path(args.out), token)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
