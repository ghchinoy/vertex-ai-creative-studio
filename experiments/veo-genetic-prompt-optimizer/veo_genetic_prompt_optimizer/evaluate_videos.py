"""Main script for running VEO video evaluations using direct API calls.
Supports both pointwise (single video) and pairwise (video comparison) modes.
"""

import json
import os
import random
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import veo_video_eval_templates

# Load environment variables from .env file
from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
# GEMINI_MODEL_ID = "gemini-2.5-flash-lite-preview-06-17"
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID")
VIDEO_EVAL_MAX_WORKERS = os.cpu_count()
SAMPLING_COUNT = 4
FLIP_ENABLED = True


def get_genai_client() -> genai.Client:
    """Initializes and returns a GenAI client."""
    try:
        return genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    except Exception as e:
        print(f"Error initializing GenAI client: {e}")
        raise


def _generate_content_with_retry(
    client: genai.Client,
    *args,
    **kwargs,
) -> genai_types.GenerateContentResponse:
    """Wrapper for generate_content with exponential backoff."""
    max_retries = 5
    base_delay = 2
    for n in range(max_retries):
        try:
            return client.models.generate_content(*args, **kwargs)
        except Exception as e:
            if "resource exhausted" in str(e).lower():
                if n < max_retries - 1:
                    delay = base_delay * (2**n) + random.uniform(0, 1)
                    print(
                        f"Resource exhausted error. Retrying in {delay:.2f} seconds...",
                    )
                    time.sleep(delay)
                else:
                    print("Max retries reached. Raising exception.")
                    raise e
            else:
                raise e


# --- Pointwise Functions ---


def evaluate_single_video(
    client: genai.Client,
    prompt: str,
    video_path: str,
    eval_id: str,
    image_path: str | None = None,
) -> dict[str, Any]:
    """Performs a pointwise evaluation of a single video, optionally with an image."""
    try:
        with open(video_path, "rb") as f:
            video_part = genai_types.Part.from_bytes(
                data=f.read(),
                mime_type="video/mp4",
            )
    except FileNotFoundError as e:
        return {"error": str(e), "score": 0, "reasoning": "File not found"}

    image_part = None
    if image_path:
        try:
            with open(image_path, "rb") as f:
                image_part = genai_types.Part.from_bytes(
                    data=f.read(),
                    mime_type="image/jpeg",
                )
        except FileNotFoundError:
            print(f"Warning: Image file {image_path} not found for evaluation.")

    api_config = genai_types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=65535,
        response_schema={
            "type": "OBJECT",
            "properties": {
                "score": {"type": "NUMBER"},
                "reasoning": {"type": "STRING"},
            },
            "required": ["score", "reasoning"],
        },
        response_mime_type="application/json",
        thinking_config=genai_types.ThinkingConfig(thinking_budget=-1),
    )

    template = (
        veo_video_eval_templates.VEO_VIDEO_REALIZATION_QUALITY_TEMPLATE_W_IMAGE
        if image_path
        else veo_video_eval_templates.VEO_VIDEO_REALIZATION_QUALITY_TEMPLATE
    )
    eval_prompt_text = template.format(prompt=prompt)
    prompt_content = [f"Evaluation ID: {eval_id}\n\n", eval_prompt_text]
    if image_part:
        prompt_content.extend(["\nReference Image:\n", image_part])
    prompt_content.extend(["\nGenerated Video:\n", video_part])

    try:
        response = _generate_content_with_retry(
            client,
            model=GEMINI_MODEL_ID,
            contents=prompt_content,
            config=api_config,
        )
        return json.loads(response.text)
    except Exception as e:
        print(f"API call error for eval_id {eval_id}: {e}")
        return {"error": str(e), "score": 0, "reasoning": f"API call failed: {e}"}


# --- Pairwise Functions ---


def compare_two_videos(
    client: genai.Client,
    prompt: str,
    video_a_path: str,
    video_b_path: str,
    eval_id: str,
    image_path: str | None = None,
    flip_order: bool = False,
) -> dict[str, Any]:
    """Performs a pairwise comparison of two videos, optionally with a reference image."""
    try:
        with open(video_a_path, "rb") as f:
            video_a_part = genai_types.Part.from_bytes(
                data=f.read(),
                mime_type="video/mp4",
            )
        with open(video_b_path, "rb") as f:
            video_b_part = genai_types.Part.from_bytes(
                data=f.read(),
                mime_type="video/mp4",
            )
    except FileNotFoundError as e:
        return {"error": str(e), "better_video": "ERROR", "reasoning": "File not found"}

    image_part = None
    if image_path:
        try:
            with open(image_path, "rb") as f:
                image_part = genai_types.Part.from_bytes(
                    data=f.read(),
                    mime_type="image/jpeg",
                )
        except FileNotFoundError:
            print(f"Warning: Image file {image_path} not found for evaluation.")

    api_config = genai_types.GenerateContentConfig(
        temperature=0.1,
        max_output_tokens=65535,
        response_schema={
            "type": "OBJECT",
            "properties": {
                "better_video": {"type": "STRING", "enum": ["A", "B", "SAME"]},
                "reasoning": {"type": "STRING"},
            },
            "required": ["better_video", "reasoning"],
        },
        response_mime_type="application/json",
        thinking_config=genai_types.ThinkingConfig(thinking_budget=-1),
    )

    template = (
        veo_video_eval_templates.PAIRWISE_VEO_VIDEO_REALIZATION_QUALITY_TEMPLATE_W_IMAGE
        if image_path
        else veo_video_eval_templates.PAIRWISE_VEO_VIDEO_REALIZATION_QUALITY_TEMPLATE
    )
    eval_prompt_text = template.format(prompt=prompt)
    prompt_content = [f"Evaluation ID: {eval_id}\n\n", eval_prompt_text]

    if image_part:
        prompt_content.extend(["\nReference Image:\n", image_part])

    if flip_order:
        prompt_content.extend(
            ["\nVideo A:\n", video_b_part, "\nVideo B:\n", video_a_part],
        )
    else:
        prompt_content.extend(
            ["\nVideo A:\n", video_a_part, "\nVideo B:\n", video_b_part],
        )

    try:
        response = _generate_content_with_retry(
            client,
            model=GEMINI_MODEL_ID,
            contents=prompt_content,
            config=api_config,
        )
        response_data = json.loads(response.text)

        if flip_order and response_data.get("better_video") in ["A", "B"]:
            response_data["better_video"] = (
                "B" if response_data["better_video"] == "A" else "A"
            )

        response_data["flipped"] = flip_order
        return response_data
    except Exception as e:
        print(f"API call error for eval_id {eval_id}: {e}")
        return {
            "error": str(e),
            "better_video": "ERROR",
            "reasoning": f"API call failed: {e}",
            "flipped": flip_order,
        }


# --- Main Execution Logic ---


def process_video_pair(
    client: genai.Client,
    prompt: str,
    video_a_path: str,
    video_b_path: str,
    sampling_count: int,
    flip_enabled: bool,
    image_path: str | None = None,
) -> dict[str, Any]:
    """Manages multiple evaluation runs for a single pair of videos."""
    if not os.path.exists(video_a_path) or not os.path.exists(video_b_path):
        return {"status": "skipped", "reason": "One or both video files not found."}

    all_votes = []
    all_comparison_results = []
    with ThreadPoolExecutor(max_workers=VIDEO_EVAL_MAX_WORKERS) as executor:
        futures = []
        for _ in range(sampling_count):
            futures.append(
                executor.submit(
                    compare_two_videos,
                    client,
                    prompt,
                    video_a_path,
                    video_b_path,
                    str(uuid.uuid4()),
                    image_path,
                    False,
                ),
            )
        if flip_enabled:
            for _ in range(sampling_count):
                futures.append(
                    executor.submit(
                        compare_two_videos,
                        client,
                        prompt,
                        video_a_path,
                        video_b_path,
                        str(uuid.uuid4()),
                        image_path,
                        True,
                    ),
                )

        for future in as_completed(futures):
            result = future.result()
            if result.get("better_video") != "ERROR":
                all_votes.append(result["better_video"])
                all_comparison_results.append(result)

    if not all_votes:
        return {"status": "error", "reason": "All evaluation API calls failed."}

    vote_counts = Counter(all_votes)
    return {
        "status": "success",
        "vote_counts": dict(vote_counts),
        "total_evals": len(all_votes),
        "individual_results": all_comparison_results,
    }


def print_summary(results: list[dict[str, Any]], processing_time: float):
    """Prints a formatted summary of the video evaluation results."""
    print("\n" + "=" * 60)
    print("VIDEO EVALUATION RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total processing time: {processing_time:.2f}s")

    for i, result in enumerate(results):
        print(f"\n--- Comparison Pair {i + 1} ---")
        print(f"  Prompt: {result['prompt'][:80]}...")
        print(f"  Video A: {os.path.basename(result['video_a'])}")
        print(f"  Video B: {os.path.basename(result['video_b'])}")

        if result["eval_results"]["status"] == "success":
            print("  Status: Success")
            print(f"  Vote Counts: {result['eval_results']['vote_counts']}")
            print(f"  Total Valid Evals: {result['eval_results']['total_evals']}")
        else:
            print(f"  Status: {result['eval_results']['status']}")
            print(f"  Reason: {result['eval_results']['reason']}")
    print("\n" + "=" * 60)


def main():
    """Main function to run the video evaluation suite."""
    client = get_genai_client()
    start_time = time.time()

    try:
        with open("augmented_prompts.json") as f:
            augmented_prompts_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading or parsing augmented_prompts.json: {e}. Exiting.")
        return

    video_pairs_to_compare = []
    video_pairs_dir = "video_pairs"
    if os.path.exists(video_pairs_dir):
        for item in augmented_prompts_data:
            original_prompt = item["original_prompt"]
            image_path = item.get("image_path")

            if image_path:
                base_name = os.path.splitext(os.path.basename(image_path))[0]
            else:
                sanitized_name = "".join(
                    c for c in original_prompt if c.isalnum() or c in " _-"
                ).rstrip()
                base_name = f"text_{sanitized_name.replace(' ', '_').lower()[:30]}"

            pair_dir = os.path.join(video_pairs_dir, base_name)

            original_video = os.path.join(pair_dir, "original.mp4")
            augmented_video = os.path.join(pair_dir, "augmented.mp4")

            if os.path.exists(original_video) and os.path.exists(augmented_video):
                video_pairs_to_compare.append(
                    {
                        "prompt": original_prompt,
                        "video_a": original_video,
                        "video_b": augmented_video,
                        "image_path": image_path,
                    },
                )

    if not video_pairs_to_compare:
        print("No valid video pairs found in the 'video_pairs' directory. Exiting.")
        return

    # --- Run Pairwise Evaluations ---
    print("\n" + "#" * 80)
    print("### RUNNING PAIRWISE VIDEO EVALUATIONS ###")
    print(f"Found {len(video_pairs_to_compare)} pairs to evaluate.")
    print("#" * 80)

    pairwise_results = []
    with ThreadPoolExecutor(max_workers=VIDEO_EVAL_MAX_WORKERS) as executor:
        future_to_pair = {
            executor.submit(
                process_video_pair,
                client,
                pair["prompt"],
                pair["video_a"],
                pair["video_b"],
                SAMPLING_COUNT,
                FLIP_ENABLED,
                pair["image_path"],
            ): pair
            for pair in video_pairs_to_compare
        }

        for future in as_completed(future_to_pair):
            pair = future_to_pair[future]
            try:
                eval_results = future.result()
                pairwise_results.append({**pair, "eval_results": eval_results})
            except Exception as exc:
                print(
                    f"Pair for prompt '{pair['prompt']}' generated an exception: {exc}",
                )
                pairwise_results.append(
                    {**pair, "eval_results": {"status": "error", "reason": str(exc)}},
                )

    print_summary(
        sorted(pairwise_results, key=lambda x: x["video_a"]),
        time.time() - start_time,
    )


if __name__ == "__main__":
    main()
