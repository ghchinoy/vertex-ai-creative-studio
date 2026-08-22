#!/usr/bin/env python3
"""generate_veo.py -- generate ONE real Veo video clip (cheapest, shortest).

Replicates the product path ``models/veo.py::generate_video``: the google-genai
``client.models.generate_videos`` long-running call with a
``GenerateVideosConfig`` whose fields mirror the product's ``gen_config_args``.
Unlike the product it does NOT set ``output_gcs_uri`` (no bucket needed here), so
the SDK returns the video inline as bytes, which we save locally.

HARD COST CONSTRAINTS (EM-approved, one-time):
  * model = veo-3.1-lite-generate-001 ONLY (cheapest variant)
  * duration = 4s (model minimum), resolution = 720p (lowest for lite)
  * number_of_videos = 1, generate_audio = False (audio adds cost)
  * generate EXACTLY ONCE -- no retries, no regeneration

This driver calls the paid API DIRECTLY -- it does not probe inline. Veo was
FREE-probed manually out-of-band first (feature/region resolution) via the
committed script ``test/veo_feature_probe.py`` before this one-time spend.

Usage:
    cd experiments/credentio-validator
    PROJECT_ID=ghchinoy-genai-sa LOCATION=us-central1 \
      python tests/migration_compare/livegen/generate_veo.py \
        --out tests/migration_compare/livegen/assets/veo.mp4
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

MODEL = "veo-3.1-lite-generate-001"     # cheapest Veo variant (EM-constrained)
DURATION_SECONDS = 4                     # model minimum
RESOLUTION = "720p"                      # lowest for lite
ASPECT_RATIO = "16:9"
DEFAULT_PROMPT = "a calm still pond at dawn, gentle ripples"


def generate(project: str, location: str, prompt: str, out: Path) -> bool:
    from google import genai
    from google.genai import types

    client = genai.Client(vertexai=True, project=project, location=location)
    cfg = types.GenerateVideosConfig(
        aspect_ratio=ASPECT_RATIO,
        number_of_videos=1,              # single sample
        duration_seconds=DURATION_SECONDS,
        resolution=RESOLUTION,
        enhance_prompt=True,             # lite requires prompt enhancement
        generate_audio=False,            # cost: no audio
        person_generation="dont_allow",
    )
    print(f"Generating ONE Veo clip: model={MODEL}, {DURATION_SECONDS}s, "
          f"{RESOLUTION}, 1 video, audio=off (project={project}, {location})...")
    op = client.models.generate_videos(model=MODEL, prompt=prompt, config=cfg)

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
        # Fallback: SDK may return a file handle needing an explicit download.
        client.files.download(file=video)
        out.write_bytes(video.video_bytes)
    print(f"Saved video -> {out} ({out.stat().st_size} bytes); uri={getattr(video,'uri',None)}")
    return True


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--prompt", default=DEFAULT_PROMPT)
    p.add_argument("--project", default=os.getenv("PROJECT_ID")
                   or os.getenv("GOOGLE_CLOUD_PROJECT"))
    p.add_argument("--location", default=os.getenv("LOCATION", "us-central1"))
    args = p.parse_args(argv)
    if not args.project:
        print("ERROR: set PROJECT_ID.", file=sys.stderr)
        return 2
    return 0 if generate(args.project, args.location, args.prompt, Path(args.out)) else 1


if __name__ == "__main__":
    raise SystemExit(main())
