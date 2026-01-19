"""A generic, script-style evaluator for VEO prompts supporting pointwise and pairwise,
single and batch evaluation modes, with custom metric support for multimodal evaluation.
"""

import json
import os
import random
import time
from typing import Any

import pandas as pd
import veo_prompt_eval_templates
import vertexai
from dotenv import load_dotenv
from google import genai
from vertexai.preview.evaluation import (
    AutoraterConfig,
    CustomMetric,
    EvalTask,
    PairwiseMetric,
    PointwiseMetric,
)

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
PROJECT_ID = os.getenv("PROJECT_ID")
AUTORATER_LOCATION = os.getenv("AUTORATER_LOCATION")
AUTORATER_MODEL_ID = os.getenv("AUTORATER_MODEL_ID")


# --- Client Initialization ---
def get_genai_client() -> genai.Client:
    """Initializes and returns a GenAI client."""
    try:
        return genai.Client(
            vertexai=True, project=PROJECT_ID, location=AUTORATER_LOCATION,
        )
    except Exception as e:
        print(f"Error initializing GenAI client: {e}")
        raise


# --- Custom Metric Functions for Multimodal Evaluation ---


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


def _get_autorater_response(
    client: genai.Client,
    prompt_parts: list[genai.types.Part],
    metric_name: str,
    response_schema: dict,
) -> dict[str, Any]:
    """Calls the autorater model with a given prompt and returns the parsed JSON response.
    """
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
        "response_mime_type": "application/json",
        "response_schema": response_schema,
    }
    config = genai.types.GenerateContentConfig(**config_dict)

    try:
        response = _generate_content_with_retry(
            client, model=AUTORATER_MODEL_ID, contents=prompt_parts, config=config,
        )
        response_json = json.loads(response.text)
        return response_json
    except Exception as e:
        print(f"  - Autorater API call failed: {e}")
        # Return a schema-compliant error response
        if "score" in response_schema["properties"]:
            return {"score": 0.0, "explanation": f"API call failed: {e}"}
        if "pairwise_choice" in response_schema["properties"]:
            return {"pairwise_choice": "ERROR", "explanation": f"API call failed: {e}"}
        return {}


def custom_metric_fn(
    instance: dict,
    client: genai.Client,
    metric_template: str,
    metric_name: str,
    response_schema: dict,
) -> dict[str, Any]:
    """The metric function for the CustomMetric. It constructs a multimodal prompt
    if an image is provided and calls the autorater.
    """
    formatted_prompt = metric_template.format(**instance)
    prompt_parts = [genai.types.Part.from_text(text=formatted_prompt)]

    image_path = instance.get("image_path")
    if image_path and pd.notna(image_path):
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
                prompt_parts.append(
                    genai.types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
                )
        except (FileNotFoundError, Exception) as e:
            print(
                f"  - Warning: Could not read image at {image_path}: {e}. Evaluating without image.",
            )

    result = _get_autorater_response(client, prompt_parts, metric_name, response_schema)

    if "score" in result:
        return {
            metric_name: result.get("score", 0.0),
            "explanation": result.get("explanation", ""),
        }
    if "pairwise_choice" in result:
        return {
            "pairwise_choice": result.get("pairwise_choice"),
            "explanation": result.get("explanation", ""),
        }
    return {}


# --- Pointwise Evaluation Functions ---


def evaluate_pointwise_single(
    prompt_data: dict[str, Any],
    metric_name: str,
    metric_template: str,
    experiment: str,
    sampling_count: int,
) -> tuple[float | None, str | None]:
    """Evaluates a single prompt, switching between PointwiseMetric for text-only
    and CustomMetric for multimodal inputs.
    """
    print(f"--- Running Pointwise Single Evaluation: {experiment} ---")
    eval_dataset = pd.DataFrame([prompt_data])

    if "metaprompt" in eval_dataset.columns:
        eval_dataset = eval_dataset.rename(columns={"metaprompt": "prompt"})
        metric_template = metric_template.replace("{metaprompt}", "{prompt}")

    has_image = (
        "image_path" in eval_dataset.columns
        and eval_dataset["image_path"].notna().any()
    )

    if has_image:
        print(
            "--- Detected image data. Using CustomMetric for multimodal evaluation. ---",
        )
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "score": {"type": "NUMBER"},
                "explanation": {"type": "STRING"},
            },
            "required": ["score", "explanation"],
        }
        client = get_genai_client()
        metric_function = lambda instance: custom_metric_fn(
            instance, client, metric_template, metric_name, response_schema,
        )
        metric = CustomMetric(name=metric_name, metric_function=metric_function)
    else:
        print("--- Text-only data detected. Using standard PointwiseMetric. ---")
        metric = PointwiseMetric(
            metric=metric_name, metric_prompt_template=metric_template,
        )

    autorater_config = AutoraterConfig(sampling_count=sampling_count)
    eval_task = EvalTask(
        dataset=eval_dataset, metrics=[metric], autorater_config=autorater_config,
    )
    result = eval_task.evaluate()

    metrics_df = result.metrics_table
    if not metrics_df.empty:
        explanation = metrics_df.iloc[0].get(f"{metric_name}/explanation", "N/A")
        score = metrics_df.iloc[0].get(f"{metric_name}/score")
        return score, explanation
    return None, "Evaluation failed to produce a result."


def evaluate_pointwise_batch(
    prompts_data: list[dict[str, Any]],
    metric_name: str,
    metric_template: str,
    experiment: str,
    sampling_count: int,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Runs a batch pointwise evaluation, switching between PointwiseMetric for text-only
    and CustomMetric for multimodal inputs.
    """
    print(f"--- Running Pointwise Batch Evaluation: {experiment} ---")
    eval_dataset = pd.DataFrame(prompts_data)

    if "metaprompt" in eval_dataset.columns:
        eval_dataset = eval_dataset.rename(columns={"metaprompt": "prompt"})
        metric_template = metric_template.replace("{metaprompt}", "{prompt}")

    has_image = (
        "image_path" in eval_dataset.columns
        and eval_dataset["image_path"].notna().any()
    )

    if has_image:
        print(
            "--- Detected image data. Using CustomMetric for multimodal evaluation. ---",
        )
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "score": {"type": "NUMBER"},
                "explanation": {"type": "STRING"},
            },
            "required": ["score", "explanation"],
        }
        client = get_genai_client()
        metric_function = lambda instance: custom_metric_fn(
            instance, client, metric_template, metric_name, response_schema,
        )
        metric = CustomMetric(name=metric_name, metric_function=metric_function)
    else:
        print("--- Text-only data detected. Using standard PointwiseMetric. ---")
        metric = PointwiseMetric(
            metric=metric_name, metric_prompt_template=metric_template,
        )

    autorater_config = AutoraterConfig(sampling_count=sampling_count)
    eval_task = EvalTask(
        dataset=eval_dataset, metrics=[metric], autorater_config=autorater_config,
    )

    result = eval_task.evaluate()
    return result.summary_metrics, result.metrics_table


# --- Pairwise Evaluation Functions ---


def evaluate_pairwise_single(
    pairwise_data: dict[str, Any],
    metric_name: str,
    metric_template: str,
    experiment: str,
    sampling_count: int,
    flip_enabled: bool,
) -> tuple[str | None, str | None]:
    """Evaluates a single pair of prompts, switching between PairwiseMetric for text-only
    and CustomMetric for multimodal inputs.
    """
    print(f"--- Running Pairwise Single Evaluation: {experiment} ---")
    eval_dataset = pd.DataFrame([pairwise_data])

    has_image = (
        "image_path" in eval_dataset.columns
        and eval_dataset["image_path"].notna().any()
    )

    if has_image:
        print(
            "--- Detected image data. Using CustomMetric for multimodal evaluation. ---",
        )
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "pairwise_choice": {"type": "STRING", "enum": ["A", "B", "SAME"]},
                "explanation": {"type": "STRING"},
            },
            "required": ["pairwise_choice", "explanation"],
        }
        client = get_genai_client()
        metric_function = lambda instance: custom_metric_fn(
            instance, client, metric_template, metric_name, response_schema,
        )
        metric = CustomMetric(name=metric_name, metric_function=metric_function)
    else:
        print("--- Text-only data detected. Using standard PairwiseMetric. ---")
        metric = PairwiseMetric(
            metric=metric_name, metric_prompt_template=metric_template,
        )

    autorater_config = AutoraterConfig(
        sampling_count=sampling_count, flip_enabled=flip_enabled,
    )
    eval_task = EvalTask(
        dataset=eval_dataset, metrics=[metric], autorater_config=autorater_config,
    )
    result = eval_task.evaluate()

    metrics_df = result.metrics_table
    if not metrics_df.empty:
        explanation = metrics_df.iloc[0].get(f"{metric_name}/explanation", "N/A")
        winner = metrics_df.iloc[0].get(f"{metric_name}/pairwise_choice")
        return winner, explanation
    return None, "Evaluation failed to produce a result."


def evaluate_pairwise_batch(
    pairwise_data: list[dict[str, Any]],
    metric_name: str,
    metric_template: str,
    experiment: str,
    sampling_count: int,
    flip_enabled: bool,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Runs a batch pairwise evaluation, switching between PairwiseMetric for text-only
    and CustomMetric for multimodal inputs.
    """
    print(f"--- Running Pairwise Batch Evaluation: {experiment} ---")
    eval_dataset = pd.DataFrame(pairwise_data)

    has_image = (
        "image_path" in eval_dataset.columns
        and eval_dataset["image_path"].notna().any()
    )

    if has_image:
        print(
            "--- Detected image data. Using CustomMetric for multimodal evaluation. ---",
        )
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "pairwise_choice": {"type": "STRING", "enum": ["A", "B", "SAME"]},
                "explanation": {"type": "STRING"},
            },
            "required": ["pairwise_choice", "explanation"],
        }
        client = get_genai_client()
        metric_function = lambda instance: custom_metric_fn(
            instance, client, metric_template, metric_name, response_schema,
        )
        metric = CustomMetric(name=metric_name, metric_function=metric_function)
    else:
        print("--- Text-only data detected. Using standard PairwiseMetric. ---")
        metric = PairwiseMetric(
            metric=metric_name, metric_prompt_template=metric_template,
        )

    autorater_config = AutoraterConfig(
        sampling_count=sampling_count, flip_enabled=flip_enabled,
    )
    eval_task = EvalTask(
        dataset=eval_dataset, metrics=[metric], autorater_config=autorater_config,
    )

    result = eval_task.evaluate()
    return result.summary_metrics, result.metrics_table


# --- Main Execution Logic (for testing) ---


def main():
    """Runs a full test of all evaluation configurations."""
    try:
        vertexai.init(project=PROJECT_ID, location=AUTORATER_LOCATION)
        print(f"Vertex AI initialized for project {PROJECT_ID} in {AUTORATER_LOCATION}")
    except Exception as e:
        print(f"Error initializing Vertex AI: {e}")
        exit()

    SAMPLING_COUNT = 1
    FLIP_ENABLED = True

    dummy_image_path = "dummy_image.jpg"
    if not os.path.exists(dummy_image_path):
        try:
            from PIL import Image

            img = Image.new("RGB", (60, 30), color="red")
            img.save(dummy_image_path)
            print(f"\nCreated dummy image: {dummy_image_path}")
        except ImportError:
            print(
                "\nCould not create dummy image. Please install Pillow (`pip install Pillow`) to run the multimodal test.",
            )
            return

    # --- Single Evaluations ---
    print("\n" + "#" * 80)
    print("### 1. POINTWISE SINGLE (TEXT-ONLY) ###")
    print("#" * 80)
    pointwise_text_template = (
        veo_prompt_eval_templates.VEO_PROMPT_EFFECTIVENESS_TEMPLATE.replace(
            "{original_prompt}", "{prompt}",
        ).replace("{augmented_prompt}", "This is the same as the original: {prompt}")
    )
    score, explanation = evaluate_pointwise_single(
        prompt_data={"prompt": "A bird flying."},
        metric_name="veo_effectiveness_single_text",
        metric_template=pointwise_text_template,
        experiment="veo-test-pointwise-single-text",
        sampling_count=SAMPLING_COUNT,
    )
    print("\n--- RESULT ---")
    print(f"Score: {score}\nExplanation: {explanation}")

    print("\n" + "#" * 80)
    print("### 2. POINTWISE SINGLE (MULTIMODAL) ###")
    print("#" * 80)
    score_mm, explanation_mm = evaluate_pointwise_single(
        prompt_data={
            "original_prompt": "a cat",
            "augmented_prompt": "a fluffy ginger cat sleeping on a red couch, animated",
            "image_path": dummy_image_path,
        },
        metric_name="veo_effectiveness_single_mm",
        metric_template=veo_prompt_eval_templates.VEO_PROMPT_EFFECTIVENESS_TEMPLATE_W_IMAGE,
        experiment="veo-test-pointwise-single-multimodal",
        sampling_count=SAMPLING_COUNT,
    )
    print("\n--- RESULT ---")
    print(f"Score: {score_mm}\nExplanation: {explanation_mm}")

    print("\n" + "#" * 80)
    print("### 3. PAIRWISE SINGLE (TEXT-ONLY) ###")
    print("#" * 80)
    winner, explanation = evaluate_pairwise_single(
        pairwise_data={
            "original_prompt": "A cat playing.",
            "baseline_model_response": "A cat playing.",
            "response": "A fluffy ginger cat chasing a laser pointer.",
        },
        metric_name="veo_effectiveness_pairwise_single_text",
        metric_template=veo_prompt_eval_templates.PAIRWISE_VEO_PROMPT_EFFECTIVENESS_TEMPLATE,
        experiment="veo-test-pairwise-single-text",
        sampling_count=SAMPLING_COUNT,
        flip_enabled=FLIP_ENABLED,
    )
    print("\n--- RESULT ---")
    print(f"Winner: {winner}\nExplanation: {explanation}")

    print("\n" + "#" * 80)
    print("### 4. PAIRWISE SINGLE (MULTIMODAL) ###")
    print("#" * 80)
    winner_mm, explanation_mm = evaluate_pairwise_single(
        pairwise_data={
            "original_prompt": "A red car",
            "baseline_model_response": "a red car driving",
            "response": "a vibrant red convertible driving along a coastal highway at sunset",
            "image_path": dummy_image_path,
        },
        metric_name="veo_effectiveness_pairwise_single_mm",
        metric_template=veo_prompt_eval_templates.PAIRWISE_VEO_PROMPT_EFFECTIVENESS_TEMPLATE_W_IMAGE,
        experiment="veo-test-pairwise-single-multimodal",
        sampling_count=SAMPLING_COUNT,
        flip_enabled=FLIP_ENABLED,
    )
    print("\n--- RESULT ---")
    print(f"Winner: {winner_mm}\nExplanation: {explanation_mm}")

    # --- Batch Evaluations ---
    print("\n" + "#" * 80)
    print("### 5. POINTWISE BATCH (TEXT-ONLY) ###")
    print("#" * 80)
    text_only_data = [
        {
            "original_prompt": "a cat",
            "augmented_prompt": "a fluffy ginger cat sleeping on a couch",
        },
        {
            "original_prompt": "a dog",
            "augmented_prompt": "a happy golden retriever playing fetch in a park",
        },
    ]
    summary, matrix = evaluate_pointwise_batch(
        prompts_data=text_only_data,
        metric_name="veo_effectiveness_text_only_batch",
        metric_template=veo_prompt_eval_templates.VEO_PROMPT_EFFECTIVENESS_TEMPLATE,
        experiment="veo-test-pointwise-batch-text",
        sampling_count=SAMPLING_COUNT,
    )
    print("\n--- RESULTS (TEXT-ONLY) ---")
    print("\nSummary Metrics:\n", summary)
    print("\nMetrics Table:\n", matrix)

    print("\n" + "#" * 80)
    print("### 6. POINTWISE BATCH (MULTIMODAL) ###")
    print("#" * 80)
    multimodal_data = [
        {
            "original_prompt": "a cat",
            "augmented_prompt": "a fluffy ginger cat sleeping on a red couch, animated",
            "image_path": dummy_image_path,
        },
        {
            "original_prompt": "a dog",
            "augmented_prompt": "a happy golden retriever playing fetch in a park with a red ball",
            "image_path": None,
        },
    ]
    summary_mm, matrix_mm = evaluate_pointwise_batch(
        prompts_data=multimodal_data,
        metric_name="veo_effectiveness_multimodal_batch",
        metric_template=veo_prompt_eval_templates.VEO_PROMPT_EFFECTIVENESS_TEMPLATE_W_IMAGE,
        experiment="veo-test-pointwise-batch-multimodal",
        sampling_count=SAMPLING_COUNT,
    )
    print("\n--- RESULTS (MULTIMODAL) ---")
    print("\nSummary Metrics:\n", summary_mm)
    print("\nMetrics Table:\n", matrix_mm)

    print("\n" + "#" * 80)
    print("### 7. PAIRWISE BATCH (TEXT-ONLY) ###")
    print("#" * 80)
    pairwise_text_data = [
        {
            "original_prompt": "a person walking",
            "baseline_model_response": "a person walking on the street",
            "response": "cinematic shot of a person walking on a cobblestone street at night under a streetlamp",
        },
        {
            "original_prompt": "a red car",
            "baseline_model_response": "a red car driving",
            "response": "a vibrant red convertible driving along a coastal highway at sunset",
        },
    ]
    summary_pw_text, matrix_pw_text = evaluate_pairwise_batch(
        pairwise_data=pairwise_text_data,
        metric_name="veo_effectiveness_pairwise_text_batch",
        metric_template=veo_prompt_eval_templates.PAIRWISE_VEO_PROMPT_EFFECTIVENESS_TEMPLATE,
        experiment="veo-test-pairwise-batch-text",
        sampling_count=SAMPLING_COUNT,
        flip_enabled=True,
    )
    print("\n--- RESULTS (PAIRWISE TEXT) ---")
    print("\nSummary Metrics:\n", summary_pw_text)
    print("\nMetrics Table:\n", matrix_pw_text)

    print("\n" + "#" * 80)
    print("### 8. PAIRWISE BATCH (MULTIMODAL) ###")
    print("#" * 80)
    pairwise_multimodal_data = [
        {
            "original_prompt": "a person walking",
            "baseline_model_response": "a person walking on the street",
            "response": "cinematic shot of a person walking on a cobblestone street at night under a streetlamp",
            "image_path": None,
        },
        {
            "original_prompt": "a red car",
            "baseline_model_response": "a red car driving",
            "response": "a vibrant red convertible driving along a coastal highway at sunset",
            "image_path": dummy_image_path,
        },
    ]
    summary_pw, matrix_pw = evaluate_pairwise_batch(
        pairwise_data=pairwise_multimodal_data,
        metric_name="veo_effectiveness_pairwise_multimodal_batch",
        metric_template=veo_prompt_eval_templates.PAIRWISE_VEO_PROMPT_EFFECTIVENESS_TEMPLATE_W_IMAGE,
        experiment="veo-test-pairwise-batch-multimodal",
        sampling_count=SAMPLING_COUNT,
        flip_enabled=True,
    )
    print("\n--- RESULTS (PAIRWISE MULTIMODAL) ---")
    print("\nSummary Metrics:\n", summary_pw)
    print("\nMetrics Table:\n", matrix_pw)
    print("\n" + "#" * 80)


if __name__ == "__main__":
    main()
