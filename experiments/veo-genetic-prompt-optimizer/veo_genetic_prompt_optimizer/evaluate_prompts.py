# -*- coding: utf-8 -*-
"""
A generic, script-style evaluator for VEO prompts supporting pointwise and pairwise,
single and batch evaluation modes, with custom metric support for multimodal evaluation.
"""

import json
import os
import pandas as pd
import time
import random
from typing import List, Dict, Tuple, Any, Optional
import vertexai
from vertexai.preview.evaluation import EvalTask, PointwiseMetric, PairwiseMetric, AutoraterConfig, CustomMetric
from google import genai

try:
    from . import config
    from . import veo_prompt_eval_templates
except ImportError:
    import config
    import veo_prompt_eval_templates


# --- Client Initialization ---
def get_genai_client() -> genai.Client:
    """Initializes and returns a GenAI client."""
    config.init_vertexai()
    return config.get_genai_client(location=config.AUTORATER_LOCATION)


# --- Custom Metric Functions for Multimodal Evaluation ---

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


def _get_autorater_response(client: genai.Client, prompt_parts: List[genai.types.Part], metric_name: str, response_schema: Dict) -> Dict[str, Any]:
    """
    Calls the autorater model with a given prompt and returns the parsed JSON response.
    """
    config_dict = {
        "temperature": 0.1,
        "top_p": 0.95,
        "max_output_tokens": 65535,
        "safety_settings": [
            genai.types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            genai.types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            genai.types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            genai.types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
        "response_mime_type": "application/json",
        "response_schema": response_schema,
    }
    cfg = genai.types.GenerateContentConfig(**config_dict)

    try:
        response = _generate_content_with_retry(client, model=config.AUTORATER_MODEL_ID, contents=prompt_parts, config=cfg)
        response_json = json.loads(response.text)
        return response_json
    except Exception as e:
        print(f"  - Autorater API call failed: {e}")
        # Return a schema-compliant error response
        if "score" in response_schema.get("properties", {}):
            return {"score": 0.0, "explanation": f"API call failed: {e}"}
        elif "pairwise_choice" in response_schema.get("properties", {}):
            return {"pairwise_choice": "ERROR", "explanation": f"API call failed: {e}"}
        return {}


def custom_metric_fn(instance: dict, client: genai.Client, metric_template: str, metric_name: str, response_schema: Dict) -> Dict[str, Any]:
    """
    The metric function for the CustomMetric. It constructs a multimodal prompt
    if an image is provided and calls the autorater.
    """
    formatted_prompt = metric_template.format(**instance)
    prompt_parts = [genai.types.Part.from_text(text=formatted_prompt)]
    
    image_path = instance.get("image_path")
    if image_path and pd.notna(image_path):
        resolved_img = config.resolve_path(str(image_path))
        try:
            with open(resolved_img, "rb") as f:
                image_data = f.read()
                prompt_parts.append(genai.types.Part.from_bytes(data=image_data, mime_type="image/jpeg"))
        except (FileNotFoundError, Exception) as e:
            print(f"  - Warning: Could not read image at {image_path}: {e}. Evaluating without image.")

    result = _get_autorater_response(client, prompt_parts, metric_name, response_schema)
    
    if "score" in result:
        return {
            metric_name: result.get("score", 0.0),
            "explanation": result.get("explanation", "")
        }
    elif "pairwise_choice" in result:
        return {
            "pairwise_choice": result.get("pairwise_choice"),
            "explanation": result.get("explanation", "")
        }
    return {}


# --- Pointwise Evaluation Functions ---

def evaluate_pointwise_single(
    prompt_data: Dict[str, Any],
    metric_name: str,
    metric_template: str,
    experiment: str,
    sampling_count: int = 1
) -> Tuple[Optional[float], Optional[str]]:
    """
    Evaluates a single prompt, switching between PointwiseMetric for text-only
    and CustomMetric for multimodal inputs.
    """
    config.init_vertexai()
    print(f"--- Running Pointwise Single Evaluation: {experiment} ---")
    eval_dataset = pd.DataFrame([prompt_data])

    if 'metaprompt' in eval_dataset.columns:
        eval_dataset = eval_dataset.rename(columns={'metaprompt': 'prompt'})
        metric_template = metric_template.replace('{metaprompt}', '{prompt}')
    
    has_image = 'image_path' in eval_dataset.columns and eval_dataset['image_path'].notna().any()

    if has_image:
        print("--- Detected image data. Using CustomMetric for multimodal evaluation. ---")
        response_schema = {
            "type": "OBJECT",
            "properties": {"score": {"type": "NUMBER"}, "explanation": {"type": "STRING"}},
            "required": ["score", "explanation"],
        }
        client = get_genai_client()
        metric_function = lambda instance: custom_metric_fn(instance, client, metric_template, metric_name, response_schema)
        metric = CustomMetric(name=metric_name, metric_function=metric_function)
    else:
        print("--- Text-only data detected. Using standard PointwiseMetric. ---")
        metric = PointwiseMetric(metric=metric_name, metric_prompt_template=metric_template)

    autorater_config = AutoraterConfig(sampling_count=sampling_count)
    eval_task = EvalTask(dataset=eval_dataset, metrics=[metric], autorater_config=autorater_config)
    result = eval_task.evaluate()
    
    metrics_df = result.metrics_table
    if not metrics_df.empty:
        explanation = metrics_df.iloc[0].get(f'{metric_name}/explanation', "N/A")
        score = metrics_df.iloc[0].get(f'{metric_name}/score')
        return score, explanation
    return None, "Evaluation failed to produce a result."


def evaluate_pointwise_batch(
    prompts_data: List[Dict[str, Any]],
    metric_name: str,
    metric_template: str,
    experiment: str,
    sampling_count: int = 1
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """
    Runs a batch pointwise evaluation, switching between PointwiseMetric for text-only
    and CustomMetric for multimodal inputs.
    """
    config.init_vertexai()
    print(f"--- Running Pointwise Batch Evaluation: {experiment} ---")
    eval_dataset = pd.DataFrame(prompts_data)

    if 'metaprompt' in eval_dataset.columns:
        eval_dataset = eval_dataset.rename(columns={'metaprompt': 'prompt'})
        metric_template = metric_template.replace('{metaprompt}', '{prompt}')
    
    has_image = 'image_path' in eval_dataset.columns and eval_dataset['image_path'].notna().any()

    if has_image:
        print("--- Detected image data. Using CustomMetric for multimodal evaluation. ---")
        response_schema = {
            "type": "OBJECT",
            "properties": {"score": {"type": "NUMBER"}, "explanation": {"type": "STRING"}},
            "required": ["score", "explanation"],
        }
        client = get_genai_client()
        metric_function = lambda instance: custom_metric_fn(instance, client, metric_template, metric_name, response_schema)
        metric = CustomMetric(name=metric_name, metric_function=metric_function)
    else:
        print("--- Text-only data detected. Using standard PointwiseMetric. ---")
        metric = PointwiseMetric(metric=metric_name, metric_prompt_template=metric_template)

    autorater_config = AutoraterConfig(sampling_count=sampling_count)
    eval_task = EvalTask(dataset=eval_dataset, metrics=[metric], autorater_config=autorater_config)
    
    result = eval_task.evaluate()
    return result.summary_metrics, result.metrics_table


# --- Pairwise Evaluation Functions ---

def evaluate_pairwise_single(
    pairwise_data: Dict[str, Any],
    metric_name: str,
    metric_template: str,
    experiment: str,
    sampling_count: int = 1,
    flip_enabled: bool = True
) -> Tuple[Optional[str], Optional[str]]:
    """
    Evaluates a single pair of prompts, switching between PairwiseMetric for text-only
    and CustomMetric for multimodal inputs.
    """
    config.init_vertexai()
    print(f"--- Running Pairwise Single Evaluation: {experiment} ---")
    eval_dataset = pd.DataFrame([pairwise_data])

    has_image = 'image_path' in eval_dataset.columns and eval_dataset['image_path'].notna().any()

    if has_image:
        print("--- Detected image data. Using CustomMetric for multimodal evaluation. ---")
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "pairwise_choice": {"type": "STRING", "enum": ["A", "B", "SAME"]},
                "explanation": {"type": "STRING"},
            },
            "required": ["pairwise_choice", "explanation"],
        }
        client = get_genai_client()
        metric_function = lambda instance: custom_metric_fn(instance, client, metric_template, metric_name, response_schema)
        metric = CustomMetric(name=metric_name, metric_function=metric_function)
    else:
        print("--- Text-only data detected. Using standard PairwiseMetric. ---")
        metric = PairwiseMetric(metric=metric_name, metric_prompt_template=metric_template)

    autorater_config = AutoraterConfig(sampling_count=sampling_count, flip_enabled=flip_enabled)
    eval_task = EvalTask(dataset=eval_dataset, metrics=[metric], autorater_config=autorater_config)
    result = eval_task.evaluate()

    metrics_df = result.metrics_table
    if not metrics_df.empty:
        explanation = metrics_df.iloc[0].get(f'{metric_name}/explanation', "N/A")
        winner = metrics_df.iloc[0].get(f'{metric_name}/pairwise_choice')
        return winner, explanation
    return None, "Evaluation failed to produce a result."


def evaluate_pairwise_batch(
    pairwise_data: List[Dict[str, Any]],
    metric_name: str,
    metric_template: str,
    experiment: str,
    sampling_count: int = 1,
    flip_enabled: bool = True
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    """
    Runs a batch pairwise evaluation, switching between PairwiseMetric for text-only
    and CustomMetric for multimodal inputs.
    """
    config.init_vertexai()
    print(f"--- Running Pairwise Batch Evaluation: {experiment} ---")
    eval_dataset = pd.DataFrame(pairwise_data)

    has_image = 'image_path' in eval_dataset.columns and eval_dataset['image_path'].notna().any()

    if has_image:
        print("--- Detected image data. Using CustomMetric for multimodal evaluation. ---")
        response_schema = {
            "type": "OBJECT",
            "properties": {
                "pairwise_choice": {"type": "STRING", "enum": ["A", "B", "SAME"]},
                "explanation": {"type": "STRING"},
            },
            "required": ["pairwise_choice", "explanation"],
        }
        client = get_genai_client()
        metric_function = lambda instance: custom_metric_fn(instance, client, metric_template, metric_name, response_schema)
        metric = CustomMetric(name=metric_name, metric_function=metric_function)
    else:
        print("--- Text-only data detected. Using standard PairwiseMetric. ---")
        metric = PairwiseMetric(metric=metric_name, metric_prompt_template=metric_template)

    autorater_config = AutoraterConfig(sampling_count=sampling_count, flip_enabled=flip_enabled)
    eval_task = EvalTask(dataset=eval_dataset, metrics=[metric], autorater_config=autorater_config)
    
    result = eval_task.evaluate()
    return result.summary_metrics, result.metrics_table


# --- Main Execution Logic (for testing) ---

def main():
    """Runs a test evaluation suite."""
    config.init_vertexai()
    SAMPLING_COUNT = config.SAMPLING_COUNT
    FLIP_ENABLED = config.FLIP_ENABLED

    dummy_image_path = "dummy_image.jpg"
    if not os.path.exists(dummy_image_path):
        try:
            from PIL import Image
            img = Image.new('RGB', (60, 30), color='red')
            img.save(dummy_image_path)
            print(f"\nCreated dummy image: {dummy_image_path}")
        except ImportError:
            print("\nCould not create dummy image. Pillow is required for multimodal test.")
            return

    print("\n" + "#"*80)
    print("### 1. POINTWISE SINGLE (TEXT-ONLY) ###")
    print("#"*80)
    pointwise_text_template = veo_prompt_eval_templates.VEO_PROMPT_EFFECTIVENESS_TEMPLATE.replace(
        '{original_prompt}', '{prompt}'
    ).replace(
        '{augmented_prompt}', 'This is the same as the original: {prompt}'
    )
    score, explanation = evaluate_pointwise_single(
        prompt_data={"prompt": "A bird flying."},
        metric_name="veo_effectiveness_single_text",
        metric_template=pointwise_text_template,
        experiment="veo-test-pointwise-single-text",
        sampling_count=SAMPLING_COUNT
    )
    print("\n--- RESULT ---")
    print(f"Score: {score}\nExplanation: {explanation}")


if __name__ == "__main__":
    main()
