"""This script generates augmented prompts based on an optimized metaprompt.
"""

import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

# Load environment variables from .env file
from dotenv import load_dotenv
from google import genai
from rewrite_prompt_for_safety import sanitize_prompt

load_dotenv()

# --- Configuration ---
PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
# GEMINI_MODEL_ID = "gemini-2.5-flash-lite-preview-06-17"
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID")
MAX_WORKERS = os.cpu_count()


def get_genai_client() -> genai.Client:
    """Initializes and returns a GenAI client."""
    try:
        return genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)
    except Exception as e:
        print(f"Error initializing GenAI client: {e}")
        raise


def _generate_content_with_retry(
    client: genai.Client, *args, **kwargs,
) -> genai.types.GenerateContentResponse:
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


def generate_with_gemini(
    client: genai.Client, prompt_text: str, image_path: str | None = None,
) -> str:
    """Generic function to call Gemini with a specific configuration, optionally including an image."""
    parts = [genai.types.Part.from_text(text=prompt_text)]
    if image_path:
        try:
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
                parts.append(genai.types.Part.from_text(text="Image to animate:"))
                parts.append(
                    genai.types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
                )
        except FileNotFoundError:
            print(f"  - Image file not found: {image_path}")
            return ""

    contents = [genai.types.Content(role="user", parts=parts)]
    config_dict = {
        "temperature": 1,
        "top_p": 0.95,
        "max_output_tokens": 65535,
        "safety_settings": [
            genai.types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF",
            ),
            genai.types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF",
            ),
            genai.types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF",
            ),
            genai.types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT", threshold="OFF",
            ),
        ],
        "thinking_config": genai.types.ThinkingConfig(thinking_budget=-1),
    }
    config = genai.types.GenerateContentConfig(**config_dict)
    try:
        response = _generate_content_with_retry(
            client, model=GEMINI_MODEL_ID, contents=contents, config=config,
        )
        return response.text
    except Exception as e:
        print(f"  - Gemini API call failed: {e}")
        return ""


def augment_prompt(
    client: genai.Client, prompt_data: dict[str, Any], optimized_metaprompt: str,
) -> dict[str, Any]:
    """Generates and sanitizes an augmented prompt, handling optional images."""
    original_prompt = prompt_data["prompt"]
    image_path = prompt_data.get("image_path")

    print(
        f"Augmenting prompt: '{original_prompt}'"
        + (f" with image {image_path}" if image_path else ""),
    )

    full_prompt = f"{optimized_metaprompt}\n\nOriginal Prompt: {original_prompt}\n\nYour output should be solely the augmented prompt text, nothing else."
    augmented_prompt = generate_with_gemini(client, full_prompt, image_path=image_path)

    result = {
        "original_prompt": original_prompt,
        "augmented_prompt": "",
        "augmented_prompt_unsanitized": "",
    }
    if image_path:
        result["image_path"] = image_path

    if augmented_prompt:
        result["augmented_prompt_unsanitized"] = augmented_prompt.strip()
        print("  - Sanitizing augmented prompt...")
        sanitized_prompt = sanitize_prompt(client, augmented_prompt)
        result["augmented_prompt"] = sanitized_prompt.strip()

    return result


def main():
    """Main function to generate augmented prompts."""
    client = get_genai_client()

    try:
        with open("optimization_history.json") as f:
            history = json.load(f)
        last_generation = history[-1]
        optimized_metaprompt = last_generation["best_parent"]["metaprompt"]
    except (FileNotFoundError, json.JSONDecodeError, IndexError, KeyError) as e:
        print(
            f"Error loading or parsing 'optimization_history.json' to get metaprompt: {e}. Exiting.",
        )
        return

    try:
        with open("original_prompts.json") as f:
            original_prompts_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading or parsing 'original_prompts.json': {e}. Exiting.")
        return

    base_prompts = [
        item
        for item in original_prompts_data
        if isinstance(item, dict) and "prompt" in item
    ]

    if not base_prompts:
        print("No valid prompts found in original_prompts.json. Exiting.")
        return

    augmented_prompts = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_prompt = {
            executor.submit(
                augment_prompt, client, prompt_data, optimized_metaprompt,
            ): prompt_data
            for prompt_data in base_prompts
        }
        for future in as_completed(future_to_prompt):
            prompt_data = future_to_prompt[future]
            try:
                result = future.result()
                if result["augmented_prompt"]:
                    augmented_prompts.append(result)
                    print(f"  - Success for: '{result['original_prompt']}'")
                else:
                    print(f"  - Failed for: '{result['original_prompt']}'")
            except Exception as exc:
                print(f"'{prompt_data['prompt']}' generated an exception: {exc}")

    with open("augmented_prompts.json", "w") as f:
        json.dump(augmented_prompts, f, indent=4)

    print("\nAugmented prompts saved to 'augmented_prompts.json'")


if __name__ == "__main__":
    main()
