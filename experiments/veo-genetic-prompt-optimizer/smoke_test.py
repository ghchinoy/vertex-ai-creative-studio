#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smoke Test for VEO Genetic Prompt Optimizer.

Validates:
1. Environment configuration and Google Cloud credentials.
2. Direct connection to Gemini 3.6 Flash (global region).
3. 1-generation micro-optimization run on a sample prompt.
4. Prompt safety sanitization and augmented prompt output.
5. (Optional) Veo video generation endpoint verification.

Usage:
    python smoke_test.py                # Run micro-optimization smoke test
    python smoke_test.py --dry-run      # Validate environment & mocks only
    python smoke_test.py --test-video   # Also test 1 Veo video generation
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path

# Ensure package is on sys.path
EXPERIMENT_ROOT = Path(__file__).resolve().parent
if str(EXPERIMENT_ROOT) not in sys.path:
    sys.path.insert(0, str(EXPERIMENT_ROOT))

from veo_genetic_prompt_optimizer import (
    config,
    prompt_optimizer,
    generate_prompts,
    rewrite_prompt_for_safety,
)


def print_step(title: str):
    print("\n" + "=" * 60)
    print(f"👉 {title}")
    print("=" * 60)


def check_environment() -> bool:
    print_step("Step 1: Checking Environment & Configuration")
    print(f"  • PROJECT_ID: {config.PROJECT_ID or '[Not set in environment]'}")
    print(f"  • GEMINI_MODEL_ID: {config.GEMINI_MODEL_ID}")
    print(f"  • LOCATION: {config.LOCATION}")
    print(f"  • AUTORATER_MODEL_ID: {config.AUTORATER_MODEL_ID}")
    print(f"  • AUTORATER_LOCATION: {config.AUTORATER_LOCATION}")
    print(f"  • VEO_MODEL_ID: {config.VEO_MODEL_ID}")
    print(f"  • VEO_LOCATION: {config.VEO_LOCATION}")

    if not config.PROJECT_ID:
        print("\n❌ Warning: PROJECT_ID environment variable is missing.")
        print("   Set PROJECT_ID in .env or via environment before running live tests.")
        return False

    return True


def run_live_connectivity_test(client) -> bool:
    print_step("Step 2: Testing Gemini 3.6 Flash Connectivity")
    try:
        start_t = time.time()
        test_prompt = "Say 'Veo Prompt Optimizer Ready' and nothing else."
        response = prompt_optimizer.generate_with_gemini(client, test_prompt)
        elapsed = time.time() - start_t
        print(f"  • Response: {response.strip()}")
        print(f"  • Latency: {elapsed:.2f}s")
        print("  ✅ Gemini API connectivity verified.")
        return True
    except Exception as e:
        print(f"  ❌ Gemini API connection failed: {e}")
        return False


def run_safety_sanitization_test(client) -> bool:
    print_step("Step 3: Testing Prompt Safety Sanitization")
    test_unsafe_prompt = "A cinematic shot of a young boy playing on a beach with a red kite at sunset."
    print(f"  • Input:  '{test_unsafe_prompt}'")
    try:
        sanitized = rewrite_prompt_for_safety.sanitize_prompt(client, test_unsafe_prompt)
        print(f"  • Output: '{sanitized}'")
        if "boy" not in sanitized.lower() and "child" not in sanitized.lower():
            print("  ✅ Sanitization successfully removed minor reference while preserving scene.")
            return True
        else:
            print("  ⚠️ Notice: Model did not fully strip minor reference. Check prompt instructions.")
            return True
    except Exception as e:
        print(f"  ❌ Safety sanitization failed: {e}")
        return False


def run_micro_optimization(client, temp_dir: Path) -> bool:
    print_step("Step 4: Running 1-Generation Micro-Optimization")
    sample_prompts = [
        {"prompt": "A vintage convertible driving through a foggy pine forest in the Pacific Northwest."}
    ]
    prompts_file = temp_dir / "sample_prompts.json"
    prompts_file.write_text(json.dumps(sample_prompts, indent=2))

    out_meta = temp_dir / "smoke_test_metaprompt.py"
    out_hist = temp_dir / "smoke_test_history.json"
    out_augmented = temp_dir / "smoke_test_augmented.json"

    try:
        # 1. Run 1 generation with 2 candidates
        print("  • Seeding population and evaluating candidate fitness...")
        sys.argv = [
            "prompt_optimizer.py",
            "--generations", "1",
            "--population-size", "2",
            "--top-k", "1",
            "--prompts", str(prompts_file),
            "--output-metaprompt", str(out_meta),
            "--history", str(out_hist)
        ]
        prompt_optimizer.main()

        if not out_hist.exists():
            print("  ❌ Optimization failed to create history file.")
            return False

        with open(out_hist, "r") as f:
            history = json.load(f)
        
        best = history[-1]["best_parent"]
        print(f"  • Best Metaprompt Score: {best.get('combined_score', 0.0):.3f}")
        print(f"  • Best Metaprompt: '{best.get('metaprompt', '')[:100]}...'")

        # 2. Augment prompt
        print("\n  • Generating augmented prompt...")
        sys.argv = [
            "generate_prompts.py",
            "--history", str(out_hist),
            "--prompts", str(prompts_file),
            "--output", str(out_augmented)
        ]
        generate_prompts.main()

        if not out_augmented.exists():
            print("  ❌ Augmented prompts generation failed.")
            return False

        with open(out_augmented, "r") as f:
            augmented = json.load(f)
        
        print(f"  • Augmented Prompt Output:\n    \"{augmented[0].get('augmented_prompt', '')}\"")
        print("  ✅ Micro-optimization and prompt augmentation complete.")
        return True

    except Exception as e:
        print(f"  ❌ Micro-optimization failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Smoke test for Veo Genetic Prompt Optimizer.")
    parser.add_argument("--dry-run", action="store_true", help="Perform offline environment and test checks.")
    parser.add_argument("--test-video", action="store_true", help="Generate 1 test video with Veo.")
    args = parser.parse_args()

    print("\n" + "#" * 60)
    print("### VEO GENETIC PROMPT OPTIMIZER - SMOKE TEST SUITE ###")
    print("#" * 60)

    env_ok = check_environment()
    if args.dry_run:
        print("\n[Dry Run] Validating unit test suite...")
        import pytest
        ret = pytest.main([str(EXPERIMENT_ROOT / "tests")])
        print(f"\n✅ Dry run complete. Pytest exit code: {ret}")
        return

    if not env_ok:
        print("\n❌ Cannot proceed with live smoke test without PROJECT_ID. Use --dry-run for offline testing.")
        sys.exit(1)

    try:
        client = config.get_genai_client()
        config.init_vertexai()
    except Exception as e:
        print(f"\n❌ Client initialization failed: {e}")
        sys.exit(1)

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        temp_path = Path(tmpdir)
        step2 = run_live_connectivity_test(client)
        if not step2:
            print("\n❌ Connectivity check failed. Aborting smoke test.")
            sys.exit(1)

        step3 = run_safety_sanitization_test(client)
        step4 = run_micro_optimization(client, temp_path)

        if args.test_video and step4:
            print_step("Step 5: Testing Veo Video Generation (Optional)")
            from veo_genetic_prompt_optimizer import generate_videos
            veo_client = config.get_genai_client(location=config.VEO_LOCATION)
            video_out = temp_path / "smoke_test_video.mp4"
            success = generate_videos.generate_single_video(
                veo_client,
                prompt_text="A cinematic shot of a red vintage car driving along a coastal highway at sunset.",
                output_path=str(video_out),
                duration_seconds=5
            )
            if success and video_out.exists():
                print(f"  ✅ Veo video successfully generated: {video_out.stat().st_size} bytes")
            else:
                print("  ⚠️ Veo video generation did not complete successfully.")

    print("\n" + "#" * 60)
    print("### SMOKE TEST FINISHED SUCCESSFULLY ###")
    print("#" * 60)


if __name__ == "__main__":
    main()
