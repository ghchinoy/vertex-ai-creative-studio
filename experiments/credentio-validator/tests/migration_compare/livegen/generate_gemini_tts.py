#!/usr/bin/env python3
"""generate_gemini_tts.py -- synthesize ONE short real Gemini-TTS utterance.

Replicates the product path ``models/gemini_tts.py::synthesize_speech``: Cloud
Text-to-Speech ``synthesize_speech`` with a Gemini TTS ``model_name`` in the
voice params and ``AudioEncoding.LINEAR16``. To avoid importing the product
module (which drags in common.analytics/config), this driver issues the SAME
request over the Text-to-Speech REST API -- the same transport-agnostic pattern
the harness already uses (it calls ``c2pa.Reader`` directly rather than importing
``services/c2pa_service.py``). The request body mirrors the product call exactly.

COST DISCIPLINE: the CHEAPEST TTS model (gemini-2.5-flash-lite-preview-tts), a
handful of characters, ONE synthesis. Cloud TTS bills per character, so a short
utterance is effectively free. FREE-probe (voices:list) runs first.

Usage:
    python tests/migration_compare/livegen/generate_gemini_tts.py \
        --out tests/migration_compare/livegen/assets/gemini_tts.wav
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

DEFAULT_MODEL = "gemini-2.5-flash-lite-preview-tts"   # cheapest TTS variant
DEFAULT_VOICE = "Kore"
DEFAULT_LANG = "en-US"
DEFAULT_TEXT = "Hello."
DEFAULT_PROMPT = "Say this cheerfully."
TTS_HOST = "https://texttospeech.googleapis.com"


def _token() -> str:
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True).strip()


def _post(url: str, body: dict, token: str) -> tuple[int, dict]:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:  # noqa: PERF203
        return e.code, json.loads(e.read().decode() or "{}")


def free_probe(model: str, lang: str, token: str) -> bool:
    """FREE probe: list voices for the model/language. No synthesis, no cost."""
    url = f"{TTS_HOST}/v1beta1/voices?languageCode={lang}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as resp:
            _ = json.loads(resp.read().decode())
            print(f"  FREE-probe voices:list [{resp.status}] OK for {lang}")
            return True
    except urllib.error.HTTPError as e:
        print(f"  FREE-probe voices:list [{e.code}] {e.read().decode()[:160]}")
        return False


def synthesize(model: str, voice: str, lang: str, text: str, prompt: str,
               out: Path, token: str) -> bool:
    body = {
        "input": {"text": text, "prompt": prompt},
        "voice": {"languageCode": lang, "name": voice, "model_name": model},
        "audioConfig": {"audioEncoding": "LINEAR16"},
    }
    print(f"Synthesizing ONE utterance with {model} (voice={voice}, "
          f"{len(text)} chars)...")
    code, resp = _post(f"{TTS_HOST}/v1beta1/text:synthesize", body, token)
    if code != 200 or "audioContent" not in resp:
        print(f"  synthesize failed [{code}]: {json.dumps(resp)[:300]}")
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(resp["audioContent"]))
    print(f"Saved LINEAR16 audio -> {out} ({out.stat().st_size} bytes)")
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--voice", default=DEFAULT_VOICE)
    p.add_argument("--lang", default=DEFAULT_LANG)
    p.add_argument("--text", default=DEFAULT_TEXT)
    p.add_argument("--prompt", default=DEFAULT_PROMPT)
    args = p.parse_args(argv)

    token = _token()
    if not free_probe(args.model, args.lang, token):
        print("FREE-probe failed; not spending.", file=sys.stderr)
        return 1
    ok = synthesize(args.model, args.voice, args.lang, args.text, args.prompt,
                    Path(args.out), token)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
