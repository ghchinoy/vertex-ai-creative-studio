#!/usr/bin/env python3
"""gen_av_fixtures.py -- generate signed VIDEO and AUDIO C2PA fixtures.

Phase 4 breadth: proves the credentio validator + our adapter handle formats
beyond JPEG. Reuses the SAME es256 sandbox signer that produced the Phase 1
signed_v2.jpg fixture, so these assets are "untrusted (sandbox)" against the
public C2PA anchors -- exercising the untrusted path as well as the format
breadth.

Requires the scratch signer material from the Phase 1 build
(/tmp/es256.pub + /tmp/es256.pem) and ffmpeg-produced base media. Not part of
the runtime package; it is a one-shot fixture generator kept for reproducibility.
"""

import json
import pathlib
import sys

import c2pa

CERT = "/tmp/es256.pub"
KEY = "/tmp/es256.pem"

TESTDATA = pathlib.Path(__file__).resolve().parent.parent / "testdata"

# (base media produced by ffmpeg, destination fixture, C2PA format string)
JOBS = [
    ("/tmp/base.mp4", TESTDATA / "signed_video.mp4", "video/mp4"),
    ("/tmp/base_audio.m4a", TESTDATA / "signed_audio.m4a", "audio/mp4"),
]


def manifest_for(fmt: str) -> dict:
    return {
        "claim_generator_info": [{"name": "credentio-spike", "version": "0.1.0"}],
        "title": f"credentio spike fixture ({fmt})",
        "format": fmt,
        "assertions": [
            {
                "label": "c2pa.actions.v2",
                "data": {
                    "actions": [
                        {
                            "action": "c2pa.created",
                            "digitalSourceType": (
                                "http://cv.iptc.org/newscodes/"
                                "digitalsourcetype/trainedAlgorithmicMedia"
                            ),
                        }
                    ]
                },
            }
        ],
    }


def main() -> int:
    cert = open(CERT).read()
    key = open(KEY).read()
    signer = c2pa.Signer.from_info(
        c2pa.C2paSignerInfo(
            alg=b"es256",
            sign_cert=cert.encode(),
            private_key=key.encode(),
            ta_url=None,
        )
    )

    for src, dst, fmt in JOBS:
        if not pathlib.Path(src).exists():
            print(f"!! base media missing: {src} (run ffmpeg first)", file=sys.stderr)
            return 1
        if dst.exists():
            dst.unlink()
        builder = c2pa.Builder.from_json(json.dumps(manifest_for(fmt)))
        builder.sign_file(src, str(dst), signer)
        with c2pa.Reader(str(dst)) as r:
            m = json.loads(r.json())
        print(f"signed -> {dst.name} ({dst.stat().st_size} bytes) "
              f"active={m.get('active_manifest')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
