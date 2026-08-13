# -*- coding: utf-8 -*-
"""
This script generates augmented prompts based on an optimized metaprompt.
"""

import json
import os
import time
import random
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

from google import genai
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from . import config
    from .rewrite_prompt_for_safety import sanitize_prompt
except ImportError:
    import config
    from rewrite_prompt_for_safety import sanitize_prompt


def get_genai_client() -> genai.Client:
    """Initializes and returns a GenAI client."""
    return config.get_genai_client(location=config.LOCATION)


def _generate_content_with_retry(client: genai.Client, *args, **kwargs) -> genai.types.GenerateContentResponse:
    """Wrapper for generate_content with exponential backoff."""
    max_retries = 5
    base_delay = 2
    for n in range(max_retries):
        try:
            return client.models.generate_content(*args, **kwargs)
        except Exception as e:
            if "resource exhausted" in str(e).lower() or "429" in str(e):
                if n < max_retries - 1:
                    delay = base_delay * (2**n) + random.uniform(0, 1)
                    print(f"Resource exhausted error. Retrying in {delay:.2f} seconds...")
                    time.sleep(delay)
                else:
                    print("Max retries reached. Raising exception.")
                    raise e
            else:
                raise e


def generate_with_gemini(
    client: genai.Client,
    prompt_text: str,
    image_path: Optional[str] = None,
    model_id: Optional[str] = None
) -> str:
    """Generic function to call Gemini with a specific configuration, optionally including an image."""
    model = model_id or config.GEMINI_MODEL_ID
    parts = [genai.types.Part.from_text(text=prompt_text)]
    if image_path:
        resolved_img = config.resolve_path(image_path)
        try:
            with open(resolved_img, "rb") as image_file:
                image_data = image_file.read()
                parts.append(genai.types.Part.from_text(text="Image to animate:"))
                parts.append(genai.types.Part.from_bytes(data=image_data, mime_type="image/jpeg"))
        except FileNotFoundError:
            print(f"  - Image file not found: {resolved_img}")
            return ""

    contents = [genai.types.Content(role="user", parts=parts)]
    config_dict = {
        "temperature": 1.0,
        "top_p": 0.95,
        "max_output_tokens": 65535,
        "safety_settings": [
            genai.types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            genai.types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            genai.types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            genai.types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
    }
    cfg = genai.types.GenerateContentConfig(**config_dict)
    try:
        response = _generate_content_with_retry(client, model=model, contents=contents, config=cfg)
        return response.text
    except Exception as e:
        print(f"  - Gemini API call failed: {e}")
        return ""


def augment_prompt(
    client: genai.Client,
    prompt_data: Dict[str, Any],
    optimized_metaprompt: str,
    model_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Generates and sanitizes an augmented prompt, handling optional images."""
    original_prompt = prompt_data["prompt"]
    image_path = prompt_data.get("image_path")
    
    print(f"Augmenting prompt: '{original_prompt}'" + (f" with image {image_path}" if image_path else ""))
    
    full_prompt = f"{optimized_metaprompt}\n\nOriginal Prompt: {original_prompt}\n\nYour output should be solely the augmented prompt text, nothing else."
    augmented_prompt = generate_with_gemini(client, full_prompt, image_path=image_path, model_id=model_id)
    
    result = {
        "original_prompt": original_prompt,
        "augmented_prompt": "",
        "augmented_prompt_unsanitized": ""
    }
    if image_path:
        result["image_path"] = image_path

    if augmented_prompt:
        result["augmented_prompt_unsanitized"] = augmented_prompt.strip()
        print(f"  - Sanitizing augmented prompt...")
        sanitized_prompt = sanitize_prompt(client, augmented_prompt, model_id=model_id)
        result["augmented_prompt"] = sanitized_prompt.strip()
    
    return result


def main():
    """Main function to generate augmented prompts."""
    parser = argparse.ArgumentParser(description="Generate augmented prompts using an optimized metaprompt.")
    parser.add_argument("--history", default="optimization_history.json", help="Path to optimization history JSON.")
    parser.add_argument("--prompts", default="original_prompts.json", help="Path to original prompts JSON.")
    parser.add_argument("--metaprompt", default=None, help="Explicit metaprompt string to use (overrides history).")
    parser.add_argument("--output", default="augmented_prompts.json", help="Path to save augmented prompts JSON.")
    parser.add_argument("--workers", type=int, default=os.cpu_count() or 4, help="Number of worker threads.")
    args, _ = parser.parse_known_args()

    client = get_genai_client()
    optimized_metaprompt = args.metaprompt

    if not optimized_metaprompt:
        resolved_history = config.resolve_path(args.history)
        try:
            with open(resolved_history, 'r') as f:
                history = json.load(f)
            last_generation = history[-1]
            optimized_metaprompt = last_generation['best_parent']['metaprompt']
        except (FileNotFoundError, json.JSONDecodeError, IndexError, KeyError) as e:
            print(f"Error loading or parsing '{resolved_history}' to get metaprompt: {e}. Exiting.")
            return

    resolved_prompts = config.resolve_path(args.prompts)
    try:
        with open(resolved_prompts, 'r') as f:
            original_prompts_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading or parsing '{resolved_prompts}': {e}. Exiting.")
        return

    base_prompts = [
        item for item in original_prompts_data
        if isinstance(item, dict) and 'prompt' in item
    ]

    if not base_prompts:
        print(f"No valid prompts found in {resolved_prompts}. Exiting.")
        return

    augmented_prompts = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_prompt = {
            executor.submit(augment_prompt, client, prompt_data, optimized_metaprompt): prompt_data
            for prompt_data in base_prompts
        }
        for future in as_completed(future_to_prompt):
            prompt_data = future_to_prompt[future]
            try:
                result = future.result()
                if result.get("augmented_prompt"):
                    augmented_prompts.append(result)
                    print(f"  - Success for: '{result['original_prompt']}'")
                else:
                    print(f"  - Failed for: '{result['original_prompt']}'")
            except Exception as exc:
                print(f"'{prompt_data['prompt']}' generated an exception: {exc}")

    output_path = config.resolve_path(args.output)
    with open(output_path, 'w') as f:
        json.dump(augmented_prompts, f, indent=4)

    print(f"\nAugmented prompts saved to '{output_path}'")


if __name__ == "__main__":
    main()
