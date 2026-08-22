#!/usr/bin/env python3
"""generate_gemini_image.py -- generate ONE real Gemini image via Vertex.

Replicates the product's dev generation path
``test/c2pa/validate_c2pa.py::generate_image`` (same google-genai Vertex client,
same ``generate_content`` + ``response_modalities=["IMAGE"]`` shape) but with the
CHEAPEST CURRENTLY-AVAILABLE image model on this project.

WHY A STANDALONE DRIVER (not the product script): ``test/c2pa/validate_c2pa.py``
hardcodes ``MODEL_ID = "gemini-3-pro-image"`` (Nano Banana Pro), which FREE-probes
as 404 (not allow-listed) on project ghchinoy-genai-sa. Per the brief, product
code must NOT be edited; this driver substitutes the nearest current cheap model
(``gemini-2.5-flash-image``, FREE-probe: countTokens -> 200) and DOCUMENTS the
substitution. Everything else mirrors the product call.

COST DISCIPLINE: ONE image, single candidate, smallest square aspect. Run exactly
once. This driver calls the paid API DIRECTLY -- it does not probe inline; the
model was FREE-probed manually out-of-band first (``:countTokens`` -> 200) via the
committed script ``test/nano_banana_2_lite_probe.py``.

Usage:
    cd experiments/credentio-validator
    PROJECT_ID=ghchinoy-genai-sa LOCATION=us-central1 \
      python tests/migration_compare/livegen/generate_gemini_image.py \
        --out tests/migration_compare/livegen/assets/gemini_image.png
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# Cheapest currently-available image model on ghchinoy-genai-sa (FREE-probed).
# Product default gemini-3-pro-image is 404 on this project; documented substitution.
DEFAULT_MODEL = "gemini-2.5-flash-image"
DEFAULT_PROMPT = "a single red circle on a white background, minimal flat vector"


def generate_image(model_id: str, prompt: str, out_path: Path,
                   project: str, location: str) -> bool:
    from google import genai
    from google.genai import types

    print(f"Generating ONE image with model {model_id} "
          f"(project={project}, location={location})...")
    client = genai.Client(vertexai=True, project=project, location=location)

    start = time.time()
    response = client.models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            candidate_count=1,  # cost discipline: exactly one candidate
        ),
    )
    print(f"Generation took {time.time() - start:.2f}s.")

    if not (response.candidates and response.candidates[0].content.parts):
        print("No candidates/parts returned.")
        return False

    for part in response.candidates[0].content.parts:
        if part.inline_data and (part.inline_data.mime_type or "").startswith("image/"):
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_bytes(part.inline_data.data)
            print(f"Saved {part.inline_data.mime_type} -> {out_path} "
                  f"({out_path.stat().st_size} bytes)")
            return True
    print("No image part found in response.")
    return False


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True, help="output image path")
    p.add_argument("--model", default=DEFAULT_MODEL)
    p.add_argument("--prompt", default=DEFAULT_PROMPT)
    p.add_argument("--project", default=os.getenv("PROJECT_ID")
                   or os.getenv("GOOGLE_CLOUD_PROJECT"))
    p.add_argument("--location", default=os.getenv("LOCATION", "us-central1"))
    args = p.parse_args(argv)

    if not args.project:
        print("ERROR: set PROJECT_ID (or GOOGLE_CLOUD_PROJECT).", file=sys.stderr)
        return 2

    ok = generate_image(args.model, args.prompt, Path(args.out),
                        args.project, args.location)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
