#!/usr/bin/env python3
"""generate_veo_min.py -- generate ONE real Veo clip for an ARBITRARY Veo model.

WS2 sibling of the P4 ``generate_veo.py`` (which hardcodes veo-3.1-lite). This
one takes ``--model`` so the WS2 inventory can cover the other reachable Veo IDs
(veo-3.1-fast-generate-001, veo-3.1-generate-001, veo-3.0-generate-preview) with
the SAME absolute-minimum cost envelope. Mirrors the product path
``models/veo.py::generate_video`` via google-genai ``generate_videos``.

HARD COST CONSTRAINTS (EM-approved, one-time, per model):
  * duration = 4s (model minimum), resolution = 720p (lowest)
  * number_of_videos = 1, generate_audio = False (audio adds cost)
  * enhance_prompt = False (absolute-minimum intent; no extra LLM rewrite step)
  * generate EXACTLY ONCE per model -- no retries, no regeneration

NOTE: the WS2 Veo clips already committed were generated with enhance_prompt=True
(the pre-review default). They are NOT regenerated -- that spend is already made,
and re-running would violate the no-regeneration rule. This default is now False
so any FUTURE run matches the absolute-minimum intent.

PROBE METHODOLOGY (corrected -- see model-c2pa-inventory.md): an empty-instances
predictLongRunning returning 400 does NOT prove the model resolves or is
authorized -- body validation precedes the access check, so an absent/unauthorized
model also 400s (a FALSE POSITIVE). The definitive, no-charge reachability test is
the real minimal call: it either succeeds (billed) or 404s at no charge.

Usage:
    python generate_veo_min.py --model veo-3.1-fast-generate-001 --out fast.mp4
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

DURATION_SECONDS = 4       # model minimum
RESOLUTION = "720p"        # lowest
ASPECT_RATIO = "16:9"
DEFAULT_PROMPT = "a calm still pond at dawn, gentle ripples"


def generate(model: str, project: str, location: str, prompt: str,
             out: Path) -> bool:
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=project, location=location)
    cfg = types.GenerateVideosConfig(
        aspect_ratio=ASPECT_RATIO,
        number_of_videos=1,
        duration_seconds=DURATION_SECONDS,
        resolution=RESOLUTION,
        enhance_prompt=False,  # absolute-minimum intent (committed clips used True; not regenerated)
        generate_audio=False,
        person_generation="dont_allow",
    )
    print(f"Generating ONE Veo clip: model={model}, {DURATION_SECONDS}s, "
          f"{RESOLUTION}, 1 video, audio=off (project={project}, {location})...")
    op = client.models.generate_videos(model=model, prompt=prompt, config=cfg)

    print("Polling operation (no retries)...")
    start = time.time()
    while not op.done:
        time.sleep(10)
        op = client.operations.get(op)
        print(f"  ... in progress ({time.time() - start:.0f}s)")
    print(f"Operation done in {time.time() - start:.0f}s.")

    if op.error:
        print(f"  generation error: {op.error}")
        return False
    result = op.result
    if getattr(result, "rai_media_filtered_count", 0):
        print(f"  content filtered: {result.rai_media_filtered_reasons}")
        return False
    vids = getattr(result, "generated_videos", None)
    if not vids:
        print("  no generated_videos in response.")
        return False

    video = vids[0].video
    out.parent.mkdir(parents=True, exist_ok=True)
    data = getattr(video, "video_bytes", None)
    if data:
        out.write_bytes(data)
    else:
        client.files.download(file=video)
        out.write_bytes(video.video_bytes)
    print(f"Saved video -> {out} ({out.stat().st_size} bytes); "
          f"uri={getattr(video, 'uri', None)}")
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--prompt", default=DEFAULT_PROMPT)
    p.add_argument("--project", default=os.getenv("PROJECT_ID")
                   or os.getenv("GOOGLE_CLOUD_PROJECT"))
    p.add_argument("--location", default=os.getenv("LOCATION", "us-central1"))
    args = p.parse_args(argv)
    if not args.project:
        print("ERROR: set PROJECT_ID.", file=sys.stderr)
        return 2
    return 0 if generate(args.model, args.project, args.location, args.prompt,
                         Path(args.out)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
