#!/usr/bin/env python3
"""generate_chirp.py -- synthesize ONE short Chirp 3 HD utterance (Cloud TTS).

Mirrors the product Chirp path (``models/chirp_3hd.py`` -> Cloud Text-to-Speech
``synthesize_speech``). Chirp 3 HD is selected purely by VOICE NAME
(e.g. ``en-US-Chirp3-HD-Zephyr``); there is NO ``model_name`` field (unlike the
Gemini-TTS path). This driver issues the same request over the Text-to-Speech
REST API.

COST DISCIPLINE: Cloud TTS bills per character; a few characters is effectively
free. FREE-probe (voices:list) runs first and also confirms the Chirp3-HD voice
exists before the (trivial) synthesis.

Usage:
    python generate_chirp.py --out chirp.wav [--voice en-US-Chirp3-HD-Zephyr]
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

DEFAULT_VOICE = "en-US-Chirp3-HD-Zephyr"   # product default voice (chirp3.go)
DEFAULT_LANG = "en-US"
DEFAULT_TEXT = "Hello."
TTS_HOST = "https://texttospeech.googleapis.com"


def _token() -> str:
    return subprocess.check_output(
        ["gcloud", "auth", "print-access-token"], text=True).strip()


def free_probe(voice: str, lang: str, token: str) -> bool:
    url = f"{TTS_HOST}/v1beta1/voices?languageCode={lang}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  FREE-probe voices:list [{e.code}] {e.read().decode()[:160]}")
        return False
    names = {v.get("name") for v in data.get("voices", [])}
    if voice in names:
        print(f"  FREE-probe voices:list [200] OK; voice '{voice}' available")
        return True
    print(f"  FREE-probe voices:list [200] but voice '{voice}' NOT found")
    return False


def synthesize(voice: str, lang: str, text: str, out: Path, token: str) -> bool:
    body = {
        "input": {"text": text},
        "voice": {"languageCode": lang, "name": voice},
        "audioConfig": {"audioEncoding": "LINEAR16"},
    }
    print(f"Synthesizing ONE Chirp3-HD utterance (voice={voice}, {len(text)} chars)...")
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{TTS_HOST}/v1beta1/text:synthesize", data=data, method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            resp_body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  synthesize failed [{e.code}]: {e.read().decode()[:300]}")
        return False
    if "audioContent" not in resp_body:
        print(f"  no audioContent: {json.dumps(resp_body)[:200]}")
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(resp_body["audioContent"]))
    print(f"Saved LINEAR16 audio -> {out} ({out.stat().st_size} bytes)")
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--voice", default=DEFAULT_VOICE)
    p.add_argument("--lang", default=DEFAULT_LANG)
    p.add_argument("--text", default=DEFAULT_TEXT)
    args = p.parse_args(argv)

    token = _token()
    if not free_probe(args.voice, args.lang, token):
        print("FREE-probe failed; not spending.", file=sys.stderr)
        return 1
    ok = synthesize(args.voice, args.lang, args.text, Path(args.out), token)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
