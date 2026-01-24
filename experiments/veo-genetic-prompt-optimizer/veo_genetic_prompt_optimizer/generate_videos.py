import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

# Load environment variables from .env file
from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
from PIL import Image

load_dotenv()

# --- Configuration ---
PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("VEO_LOCATION")
VEO_MODEL_ID = os.getenv("VEO_MODEL_ID")
VIDEO_DURATION_SECONDS = 5
VEO_OUTPUT_DIR = "video_pairs"
GENERATED_PROMPTS_JSON = "augmented_prompts.json"
VIDEO_GEN_MAX_WORKERS = 4


def get_genai_client() -> genai.Client:
    """Initializes and returns a GenAI client."""
    try:
        return genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    except Exception as e:
        print(f"Error initializing GenAI client: {e}")
        raise


def generate_single_video(
    client: genai.Client,
    prompt_text: str,
    output_path: str,
    image_path: str | None = None,
    max_retries=3,
    enhance_prompt=False,
):
    """Generates a video from a prompt, optionally with an image."""
    if not prompt_text:
        print(f"Skipping video generation for {output_path} due to empty prompt.")
        return False

    input_image = None
    aspect_ratio = "16:9"

    if image_path:
        try:
            with Image.open(image_path) as pil_image:
                width, height = pil_image.size
                aspect_ratio = "9:16" if height > width else "16:9"
            input_image = genai_types.Image.from_file(location=image_path)
        except FileNotFoundError:
            print(
                f"Error: Image file not found at {image_path}. Skipping video generation.",
            )
            return False
        except Exception as e:
            print(f"Error opening image {image_path}: {e}. Skipping video generation.")
            return False

    base_delay = 5  # seconds
    for attempt in range(max_retries):
        try:
            generate_videos_kwargs = {
                "model": VEO_MODEL_ID,
                "prompt": prompt_text,
                "config": genai_types.GenerateVideosConfig(
                    duration_seconds=VIDEO_DURATION_SECONDS,
                    aspect_ratio=aspect_ratio,
                    number_of_videos=1,
                    enhance_prompt=enhance_prompt,
                    person_generation="allow_adult",
                ),
            }
            if input_image:
                generate_videos_kwargs["image"] = input_image

            print(
                f"Submitting request for '{os.path.basename(output_path)}' (Attempt {attempt + 1}/{max_retries})...",
            )
            operation = client.models.generate_videos(**generate_videos_kwargs)

            print(f"  - Waiting for '{os.path.basename(output_path)}' to complete...")
            while not operation.done:
                time.sleep(10)
                operation = client.operations.get(operation)

            if operation.error:
                error_message = str(operation.error).lower()
                print(
                    f"  - Error generating video {os.path.basename(output_path)}: {operation.error}",
                )
                if (
                    "internal error" in error_message
                    or "resource exhausted" in error_message
                    or "quota exceeded" in error_message
                ) and attempt < max_retries - 1:
                    delay = base_delay * (2**attempt) + random.uniform(0, 1)
                    print(
                        f"  - Retrying after operation error in {delay:.2f} seconds...",
                    )
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
            print(
                f"Exception during video generation for {os.path.basename(output_path)}: {e}",
            )
            if (
                "internal error" in error_message
                or "resource exhausted" in error_message
                or "quota exceeded" in error_message
            ) and attempt < max_retries - 1:
                delay = base_delay * (2**attempt) + random.uniform(0, 1)
                print(f"  - Retrying after exception in {delay:.2f} seconds...")
                time.sleep(delay)
                continue
            return False

    print(
        f"Failed to generate video {os.path.basename(output_path)} after {max_retries} attempts.",
    )
    return False


def process_prompt_item(client: genai.Client, prompt_item: dict[str, Any]):
    """Processes a single item from the prompts file to generate original and augmented videos."""
    original_prompt = prompt_item.get("original_prompt")
    augmented_prompt = prompt_item.get("augmented_prompt")
    image_path = prompt_item.get("image_path")

    if image_path:
        print(f"\n--- Processing Pair for Image: {image_path} ---")
        base_name = os.path.splitext(os.path.basename(image_path))[0]
    else:
        sanitized_name = "".join(
            c for c in original_prompt if c.isalnum() or c in " _-"
        ).rstrip()
        base_name = f"text_{sanitized_name.replace(' ', '_').lower()[:30]}"
        print(f"\n--- Processing Pair for Text Prompt: {base_name} ---")

    output_dir = os.path.join(VEO_OUTPUT_DIR, base_name)
    os.makedirs(output_dir, exist_ok=True)

    # Generate original video
    if original_prompt:
        generate_single_video(
            client,
            original_prompt,
            os.path.join(output_dir, "original.mp4"),
            image_path=image_path,
        )

    # Generate augmented video
    if augmented_prompt:
        generate_single_video(
            client,
            augmented_prompt,
            os.path.join(output_dir, "augmented.mp4"),
            image_path=image_path,
        )


def main():
    """Loads prompts and generates video pairs in parallel."""
    client = get_genai_client()

    try:
        with open(GENERATED_PROMPTS_JSON) as f:
            prompts_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading {GENERATED_PROMPTS_JSON}: {e}. Exiting.")
        return

    if not prompts_data:
        print("No prompt data to generate. Check your JSON file.")
        return

    print(f"Found {len(prompts_data)} prompt items to process.")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=VIDEO_GEN_MAX_WORKERS) as executor:
        futures = [
            executor.submit(process_prompt_item, client, item) for item in prompts_data
        ]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"A video generation process failed: {e}")

    end_time = time.time()
    print("\n" + "=" * 80)
    print("### VIDEO GENERATION COMPLETE ###")
    print(f"Total time taken: {end_time - start_time:.2f} seconds.")
    print(f"Videos saved in '{VEO_OUTPUT_DIR}' directory.")
    print("=" * 80)


if __name__ == "__main__":
    main()
