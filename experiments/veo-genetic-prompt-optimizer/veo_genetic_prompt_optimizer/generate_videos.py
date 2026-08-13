# -*- coding: utf-8 -*-
"""
Generates videos from prompts (and optional reference images) using the Veo model.
"""

import os
import json
import time
import random
import argparse
from pathlib import Path
from typing import Optional, Dict, Any
from PIL import Image
from google import genai
from google.genai import types as genai_types
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from . import config
except ImportError:
    import config


def get_genai_client() -> genai.Client:
    """Initializes and returns a GenAI client for Veo."""
    return config.get_genai_client(location=config.VEO_LOCATION)


def generate_single_video(
    client: genai.Client,
    prompt_text: str,
    output_path: str,
    image_path: Optional[str] = None,
    max_retries: int = 3,
    enhance_prompt: bool = False,
    duration_seconds: Optional[int] = None,
    model_id: Optional[str] = None,
) -> bool:
    """
    Generates a video from a prompt, optionally with an image.
    """
    if not prompt_text:
        print(f"Skipping video generation for {output_path} due to empty prompt.")
        return False

    duration = duration_seconds or config.VIDEO_DURATION_SECONDS
    model = model_id or config.VEO_MODEL_ID
    input_image = None
    aspect_ratio = "16:9"

    if image_path:
        resolved_img = config.resolve_path(image_path)
        try:
            with Image.open(resolved_img) as pil_image:
                width, height = pil_image.size
                aspect_ratio = "9:16" if height > width else "16:9"
            input_image = genai_types.Image.from_file(location=str(resolved_img))
        except FileNotFoundError:
            print(f"Error: Image file not found at {resolved_img}. Skipping video generation.")
            return False
        except Exception as e:
            print(f"Error opening image {resolved_img}: {e}. Skipping video generation.")
            return False

    base_delay = 5  # seconds
    for attempt in range(max_retries):
        try:
            generate_videos_kwargs = {
                "model": model,
                "prompt": prompt_text,
                "config": genai_types.GenerateVideosConfig(
                    duration_seconds=duration,
                    aspect_ratio=aspect_ratio,
                    number_of_videos=1,
                    enhance_prompt=enhance_prompt,
                    person_generation="allow_adult",
                ),
            }
            if input_image:
                generate_videos_kwargs["image"] = input_image

            print(f"Submitting request for '{os.path.basename(output_path)}' (Attempt {attempt + 1}/{max_retries})...")
            operation = client.models.generate_videos(**generate_videos_kwargs)

            print(f"  - Waiting for '{os.path.basename(output_path)}' to complete...")
            poll_count = 0
            max_polls = 120  # ~20 minutes timeout
            while not operation.done and poll_count < max_polls:
                time.sleep(10)
                poll_count += 1
                operation = client.operations.get(operation)

            if not operation.done:
                print(f"  - Timeout waiting for video generation for {output_path}.")
                return False

            if operation.error:
                error_message = str(operation.error).lower()
                print(f"  - Error generating video {os.path.basename(output_path)}: {operation.error}")
                if any(k in error_message for k in ["internal error", "resource exhausted", "quota exceeded", "429"]) and attempt < max_retries - 1:
                    delay = base_delay * (2**attempt) + random.uniform(0, 1)
                    print(f"  - Retrying after operation error in {delay:.2f} seconds...")
                    time.sleep(delay)
                    continue
                return False

            video_bytes = operation.response.generated_videos[0].video.video_bytes
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(video_bytes)

            print(f"Video saved to: {output_path}")
            return True

        except Exception as e:
            error_message = str(e).lower()
            print(f"Exception during video generation for {os.path.basename(output_path)}: {e}")
            if any(k in error_message for k in ["internal error", "resource exhausted", "quota exceeded", "429"]) and attempt < max_retries - 1:
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                print(f"  - Retrying after exception in {delay:.2f} seconds...")
                time.sleep(delay)
                continue
            return False

    print(f"Failed to generate video {os.path.basename(output_path)} after {max_retries} attempts.")
    return False


def process_prompt_item(client: genai.Client, prompt_item: Dict[str, Any], output_dir_base: str = "video_pairs") -> None:
    """
    Processes a single item from the prompts file to generate original and augmented videos.
    """
    original_prompt = prompt_item.get('original_prompt')
    augmented_prompt = prompt_item.get('augmented_prompt')
    image_path = prompt_item.get('image_path')

    if image_path:
        print(f"\n--- Processing Pair for Image: {image_path} ---")
        base_name = os.path.splitext(os.path.basename(image_path))[0]
    else:
        sanitized_name = "".join(c for c in (original_prompt or "video") if c.isalnum() or c in " _-").rstrip()
        base_name = f"text_{sanitized_name.replace(' ', '_').lower()[:30]}"
        print(f"\n--- Processing Pair for Text Prompt: {base_name} ---")

    output_dir = os.path.join(output_dir_base, base_name)
    os.makedirs(output_dir, exist_ok=True)

    # Generate original video
    if original_prompt:
        generate_single_video(
            client,
            original_prompt,
            os.path.join(output_dir, "original.mp4"),
            image_path=image_path
        )
    
    # Generate augmented video
    if augmented_prompt:
        generate_single_video(
            client,
            augmented_prompt,
            os.path.join(output_dir, "augmented.mp4"),
            image_path=image_path
        )


def main(prompts_file: str = "augmented_prompts.json", output_dir: str = "video_pairs", max_workers: int = 4):
    """
    Loads prompts and generates video pairs in parallel.
    """
    parser = argparse.ArgumentParser(description="Generate videos from augmented prompts.")
    parser.add_argument("--prompts", default=prompts_file, help="Path to augmented prompts JSON file.")
    parser.add_argument("--output-dir", default=output_dir, help="Directory to save generated videos.")
    parser.add_argument("--max-workers", type=int, default=max_workers, help="Concurrent worker count.")
    args, _ = parser.parse_known_args()

    client = get_genai_client()
    resolved_prompts_file = config.resolve_path(args.prompts)

    try:
        with open(resolved_prompts_file, 'r') as f:
            prompts_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading {resolved_prompts_file}: {e}. Exiting.")
        return

    if not prompts_data:
        print("No prompt data to generate. Check your JSON file.")
        return

    print(f"Found {len(prompts_data)} prompt items to process.")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=args.max_workers) as executor:
        futures = [executor.submit(process_prompt_item, client, item, args.output_dir) for item in prompts_data]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"A video generation process failed: {e}")

    end_time = time.time()
    print("\n" + "="*80)
    print("### VIDEO GENERATION COMPLETE ###")
    print(f"Total time taken: {end_time - start_time:.2f} seconds.")
    print(f"Videos saved in '{args.output_dir}' directory.")
    print("="*80)


if __name__ == "__main__":
    main()
