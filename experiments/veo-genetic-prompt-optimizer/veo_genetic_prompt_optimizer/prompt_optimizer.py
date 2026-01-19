"""Main script for the evolutionary optimization of VEO metaprompts.
"""

import json
import os
import random
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import evaluate_prompts
import evaluate_videos
import generate_videos
import metaprompt as metaprompt_file
import veo_prompt_eval_templates

# Load environment variables from .env file
from dotenv import load_dotenv
from google import genai

load_dotenv()

# --- Configuration ---
PROJECT_ID = os.getenv("PROJECT_ID")
LOCATION = os.getenv("LOCATION")
# GEMINI_MODEL_ID = "gemini-2.5-flash-lite-preview-06-17"
GEMINI_MODEL_ID = os.getenv("GEMINI_MODEL_ID")
NUM_GENERATIONS = 5
POPULATION_SIZE = 10
TOP_K_SELECTION = 2
AUGMENTED_PROMPT_SCORE_WEIGHT = 0.4
METAPROMPT_SCORE_WEIGHT = 0.3
INTENT_PRESERVATION_SCORE_WEIGHT = 0.3
ENABLE_VIDEO_FEEDBACK = False


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


def get_veo_prompting_guide() -> str:
    """Returns the VEO prompting guide."""
    with open("veo_guide.md") as f:
        return f.read()


def generate_with_gemini(
    client: genai.Client,
    prompt_text: str,
    image_path: str | None = None,
    response_schema: dict[str, Any] | None = None,
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
    if response_schema is not None:
        config_dict["response_mime_type"] = "application/json"
        config_dict["response_schema"] = response_schema

    config = genai.types.GenerateContentConfig(**config_dict)
    try:
        response = _generate_content_with_retry(
            client, model=GEMINI_MODEL_ID, contents=contents, config=config,
        )
        return response.text
    except Exception as e:
        print(f"  - Gemini API call failed: {e}")
        return ""


def generate_initial_population(
    client: genai.Client, base_metaprompt: str, size: int,
) -> list[dict[str, Any]]:
    """Generates the initial population of metaprompts as dictionaries with provenance."""
    print("--- Generating Initial Metaprompt Population ---")
    population = [
        {"metaprompt": base_metaprompt, "provenance": {"type": "initial_base"}},
    ]

    variation_prompt = f"""
    You are a creative assistant. Based on the following metaprompt, generate {size - 1} slightly different but plausible variations.
    These variations should explore different ways to instruct an AI to augment a prompt.
    Do not deviate too much from the original intent.

    Original Metaprompt:
    "{base_metaprompt}"
    """

    array_schema = {
        "type": "ARRAY",
        "items": {"type": "STRING"},
        "minItems": size - 1,
        "maxItems": size - 1,
    }
    response_text = generate_with_gemini(
        client, variation_prompt, response_schema=array_schema,
    )

    variations = []
    if response_text:
        try:
            variations = json.loads(response_text)
            print(f"Generated {len(variations)} variations.")
        except json.JSONDecodeError:
            print(
                "  - Error: Gemini did not return a valid JSON array. Using fallback.",
            )
    else:
        print(
            "  - Error generating initial population, using simple variations as fallback.",
        )

    if not variations:
        variations = [
            base_metaprompt + f" (variation {i + 1})" for i in range(size - 1)
        ]

    for var in variations:
        population.append(
            {"metaprompt": var, "provenance": {"type": "initial_variation"}},
        )

    return population[:size]


def _get_video_paths(prompt_data: dict[str, Any]) -> tuple[str, str, str]:
    """Generates standardized video paths for original and augmented prompts."""
    video_pairs_dir = "video_pairs"
    if prompt_data.get("image_path"):
        base_name = os.path.splitext(os.path.basename(prompt_data["image_path"]))[0]
    else:
        sanitized_name = "".join(
            c for c in prompt_data["prompt"] if c.isalnum() or c in " _-"
        ).rstrip()
        base_name = f"text_{sanitized_name.replace(' ', '_').lower()[:30]}"

    pair_dir = os.path.join(video_pairs_dir, base_name)
    os.makedirs(pair_dir, exist_ok=True)  # Ensure directory exists

    original_video_path = os.path.join(pair_dir, "original.mp4")
    augmented_video_path = os.path.join(pair_dir, "augmented.mp4")

    return original_video_path, augmented_video_path, pair_dir


def get_metaprompt_fitness(
    client: genai.Client,
    candidate_metaprompt: str,
    base_prompts: list[dict[str, Any]],  # Now a list of dicts
) -> dict[str, Any]:
    """Calculates the fitness of a single metaprompt by evaluating its instructional
    quality, the effectiveness of the prompts it generates, and its ability
    to preserve the original user intent.
    """
    print(f"\n--- Evaluating Metaprompt ---\n'{candidate_metaprompt[:100]}...'")

    # --- Step 1: Direct Metaprompt Evaluation ---
    print("  - Evaluating metaprompt instructional quality...")
    meta_summary, meta_matrix = evaluate_prompts.evaluate_pointwise_batch(
        prompts_data=[{"metaprompt": candidate_metaprompt}],
        metric_name="metaprompt_effectiveness",
        metric_template=veo_prompt_eval_templates.METAPROMPT_EFFECTIVENESS_TEMPLATE,
        experiment="metaprompt-quality-check",
        sampling_count=1,
    )
    metaprompt_score = meta_summary.get("metaprompt_effectiveness/mean", 0.0)
    metaprompt_explanation = (
        meta_matrix["metaprompt_effectiveness/explanation"].iloc[0]
        if not meta_matrix.empty
        else "Evaluation failed"
    )
    print(f"  - Instructional Quality Score: {metaprompt_score:.3f}")

    # --- Step 2: Generate Augmented Prompts ---
    print("  - Generating augmented prompts...")
    augmented_prompts_data = []
    for item in base_prompts:
        original_prompt = item["prompt"]
        image_path = item.get("image_path")

        full_prompt = f"{candidate_metaprompt}\n\nOriginal Prompt: {original_prompt}\n\nYour output should be solely the augmented prompt text, nothing else."
        augmented_prompt = generate_with_gemini(
            client, full_prompt, image_path=image_path,
        )

        if augmented_prompt:
            augmented_prompts_data.append(
                {
                    "original_prompt": original_prompt,
                    "augmented_prompt": augmented_prompt,
                    "image_path": image_path,
                },
            )
        else:
            print(f"  - Failed to generate augmented prompt for '{original_prompt}'")

    # --- Step 3: Evaluate Augmented Prompts for Effectiveness and Intent Preservation ---
    avg_effectiveness_score = 0.0
    aggregated_effectiveness_explanation = "No prompts to evaluate."
    avg_intent_score = 0.0
    aggregated_intent_explanation = "No prompts to evaluate."

    if augmented_prompts_data:
        # Check if any of the base prompts included an image path
        has_images = any(item.get("image_path") for item in base_prompts)

        effectiveness_template = (
            veo_prompt_eval_templates.VEO_PROMPT_EFFECTIVENESS_TEMPLATE_W_IMAGE
            if has_images
            else veo_prompt_eval_templates.VEO_PROMPT_EFFECTIVENESS_TEMPLATE
        )
        intent_template = (
            veo_prompt_eval_templates.VEO_PROMPT_INTENT_PRESERVATION_TEMPLATE_W_IMAGE
            if has_images
            else veo_prompt_eval_templates.VEO_PROMPT_INTENT_PRESERVATION_TEMPLATE
        )

        print("  - Evaluating augmented prompts for effectiveness...")
        eff_summary, eff_matrix = evaluate_prompts.evaluate_pointwise_batch(
            prompts_data=augmented_prompts_data,
            metric_name="veo_effectiveness",
            metric_template=effectiveness_template,
            experiment="optimizer-effectiveness-check",
            sampling_count=1,
        )
        avg_effectiveness_score = eff_summary.get("veo_effectiveness/mean", 0.0)
        aggregated_effectiveness_explanation = " | ".join(
            eff_matrix["veo_effectiveness/explanation"].tolist(),
        )
        print(f"  - Avg Effectiveness Score: {avg_effectiveness_score:.3f}")

        print("  - Evaluating augmented prompts for intent preservation...")
        intent_summary, intent_matrix = evaluate_prompts.evaluate_pointwise_batch(
            prompts_data=augmented_prompts_data,
            metric_name="intent_preservation",
            metric_template=intent_template,
            experiment="optimizer-intent-check",
            sampling_count=1,
        )
        avg_intent_score = intent_summary.get("intent_preservation/mean", 0.0)
        aggregated_intent_explanation = " | ".join(
            intent_matrix["intent_preservation/explanation"].tolist(),
        )
        print(f"  - Avg Intent Preservation Score: {avg_intent_score:.3f}")

    return {
        "augmented_prompt_score": avg_effectiveness_score,
        "augmented_prompt_explanation": aggregated_effectiveness_explanation,
        "intent_preservation_score": avg_intent_score,
        "intent_preservation_explanation": aggregated_intent_explanation,
        "metaprompt_score": metaprompt_score,
        "metaprompt_explanation": metaprompt_explanation,
        "augmented_prompts": augmented_prompts_data,
    }


def _get_selection_from_gemini(
    client: genai.Client, candidates: list[dict[str, Any]], top_k: int,
) -> dict[str, Any]:
    """Uses Gemini to rank and select top metaprompts from a list of candidates with tied scores."""
    print(f"  - Scores are tied. Using Gemini as a judge to select top {top_k}...")

    selection_schema = {
        "type": "OBJECT",
        "properties": {
            "ranked_parents": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "rank": {"type": "INTEGER"},
                        "metaprompt": {"type": "STRING"},
                        "reasoning": {"type": "STRING"},
                    },
                    "required": ["rank", "metaprompt", "reasoning"],
                },
                "minItems": top_k,
                "maxItems": top_k,
            },
            "best_parent": {
                "type": "OBJECT",
                "properties": {
                    "metaprompt": {"type": "STRING"},
                    "reasoning": {"type": "STRING"},
                },
                "required": ["metaprompt", "reasoning"],
            },
        },
        "required": ["ranked_parents", "best_parent"],
    }

    candidates_text = "\n\n".join(
        [
            (
                f'Metaprompt: "{c["metaprompt"]}"\n'
                f"  - Combined Score: {c.get('combined_score', 'N/A'):.3f}\n"
                f"  - Augmented Prompt Score: {c.get('augmented_prompt_score', 'N/A'):.3f}\n"
                f"  - Intent Preservation Score: {c.get('intent_preservation_score', 'N/A'):.3f}\n"
                f"  - Instructional Quality Score: {c.get('metaprompt_score', 'N/A'):.3f}\n"
                f'  - Augmented Prompt Feedback: "{c.get("augmented_prompt_explanation", "N/A")}"\n'
                f'  - Intent Preservation Feedback: "{c.get("intent_preservation_explanation", "N/A")}"\n'
                f'  - Instructional Quality Feedback: "{c.get("metaprompt_explanation", "N/A")}"'
            )
            for c in candidates
        ],
    )

    judge_prompt = f"""
    You are an expert judge in an evolutionary algorithm. Your task is to analyze {len(candidates)} candidate metaprompts that have achieved similar fitness scores and select the most promising ones for the next generation.

    **Primary Judging Criteria:**
    You must act as an expert evaluator. Use the following detailed rubric to guide your decision. The best metaprompt is the one that provides instructions most likely to result in rewrites that excel according to these criteria. Analyze the candidate's text and its evaluation feedback. A high score for instructional quality and intent preservation is very important.

    --- START RUBRIC ---
    ## Criteria
    1.  **Intent Preservation**: Does the metaprompt guide the AI to retain every core subject, action, and concept from the original query?
    2.  **Detail Enrichment & Creativity**: Does the metaprompt encourage adding specific and believable details?
    3.  **Cinematic & Technical Language**: Does the metaprompt effectively guide the use of camera angles, composition, and movement?
    --- END RUBRIC ---

    **Candidate Metaprompts to Evaluate:**
    Here are the candidates and their performance data. Analyze the metaprompt's text and all sets of feedback in light of the rubric above.

    {candidates_text}

    **Your Decision:**
    Based on your analysis, provide a ranked list of the top {top_k} metaprompts that should be parents for the next generation. Also, identify the single best parent overall, which should be the one with the highest potential for generating even better offspring.

    Your output must be a JSON object matching this schema:
    {json.dumps(selection_schema, indent=2)}
    """

    response_text = generate_with_gemini(
        client, judge_prompt, response_schema=selection_schema,
    )
    try:
        return json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        print(
            "  - Gemini judge failed to return valid JSON. Falling back to random selection.",
        )
        selected = random.sample(candidates, top_k)
        best = random.choice(selected)
        return {
            "ranked_parents": [
                {
                    "metaprompt": p["metaprompt"],
                    "reasoning": "Random fallback selection due to JSON error.",
                }
                for p in selected
            ],
            "best_parent": {
                "metaprompt": best["metaprompt"],
                "reasoning": "Random fallback selection due to JSON error.",
            },
        }


def select_parents(
    client: genai.Client, fitness_results: list[dict[str, Any]], top_k: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Selects the top k parents from the fitness results, using a combined score
    and Gemini as a judge for ties.
    """
    if not fitness_results:
        return [], {}

    # Calculate a combined score for each candidate
    for r in fitness_results:
        aug_score = r.get("augmented_prompt_score", 0.0)
        meta_score = r.get("metaprompt_score", 0.0)
        intent_score = r.get("intent_preservation_score", 0.0)
        r["combined_score"] = (
            (AUGMENTED_PROMPT_SCORE_WEIGHT * aug_score)
            + (METAPROMPT_SCORE_WEIGHT * meta_score)
            + (INTENT_PRESERVATION_SCORE_WEIGHT * intent_score)
        )

    # Primary sort key is the new combined score
    fitness_results.sort(key=lambda x: x.get("combined_score", 0.0), reverse=True)
    print("\n--- Candidate Ranking (Combined Score) ---")
    for i, r in enumerate(fitness_results):
        print(
            f"{i + 1}. Combined Score: {r['combined_score']:.3f} "
            f"(Aug: {r.get('augmented_prompt_score', 0):.2f}, "
            f"Meta: {r.get('metaprompt_score', 0):.2f}, "
            f"Intent: {r.get('intent_preservation_score', 0):.2f}) - "
            f"Metaprompt: '{r['metaprompt'][:80]}...'",
        )

    # Determine if a judge is needed for ambiguity in selecting the top_k parents
    use_judge = False
    if len(fitness_results) > top_k:
        score_at_cutoff = fitness_results[top_k - 1].get("combined_score", 0.0)
        score_after_cutoff = fitness_results[top_k].get("combined_score", 0.0)
        if abs(score_at_cutoff - score_after_cutoff) < 1e-9:
            use_judge = True

    # Also use judge if there's a tie for the absolute top spot
    if not use_judge and len(fitness_results) > 1:
        if (
            abs(
                fitness_results[0].get("combined_score", 0.0)
                - fitness_results[1].get("combined_score", 0.0),
            )
            < 1e-9
        ):
            use_judge = True

    if use_judge:
        print(
            "\n  - Tie detected among top candidates based on combined score. Using Gemini as a judge.",
        )
        cutoff_score = fitness_results[top_k - 1].get("combined_score", 0.0)
        candidates_to_judge = [
            r
            for r in fitness_results
            if abs(r.get("combined_score", 0.0) - cutoff_score) < 1e-9
            or r.get("combined_score", 0.0) > cutoff_score
        ]

        selection = _get_selection_from_gemini(client, candidates_to_judge, top_k)

        metaprompt_map = {r["metaprompt"]: r for r in fitness_results}

        ranked_metaprompts = [
            p["metaprompt"] for p in selection.get("ranked_parents", [])
        ]
        parents = [
            metaprompt_map[mp] for mp in ranked_metaprompts if mp in metaprompt_map
        ]

        best_parent_metaprompt = selection.get("best_parent", {}).get("metaprompt")
        best_parent = metaprompt_map.get(best_parent_metaprompt)

        if best_parent:
            best_parent["judgement"] = selection.get("best_parent", {}).get("reasoning")
        else:
            best_parent = parents[0] if parents else {}
    else:
        print("\n  - Selecting top parents based on combined scores.")
        parents = fitness_results[:top_k]
        best_parent = parents[0] if parents else {}

    return parents, best_parent


def main():
    """Main evolutionary loop."""
    client = get_genai_client()

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

    population = generate_initial_population(
        client, metaprompt_file.original_metaprompt, POPULATION_SIZE,
    )
    all_generations_results = []

    for gen in range(NUM_GENERATIONS):
        print("\n" + "=" * 80)
        print(f"### STARTING GENERATION {gen + 1}/{NUM_GENERATIONS} ###")
        print("=" * 80)

        evaluated_candidates = []
        with ThreadPoolExecutor() as executor:
            future_to_candidate = {
                executor.submit(
                    get_metaprompt_fitness,
                    client,
                    candidate["metaprompt"],
                    base_prompts,
                ): candidate
                for candidate in population
            }
            for future in as_completed(future_to_candidate):
                candidate = future_to_candidate[future]
                try:
                    fitness_data = future.result()
                    if fitness_data:
                        candidate.update(fitness_data)
                        evaluated_candidates.append(candidate)
                except Exception as exc:
                    print(
                        f"'{candidate.get('metaprompt', 'Unknown metaprompt')}' generated an exception: {exc}",
                    )
                    raise exc

        if not evaluated_candidates:
            print("No metaprompts were successfully evaluated. Stopping.")
            break

        parents, best_parent = select_parents(
            client, evaluated_candidates, TOP_K_SELECTION,
        )

        if not parents:
            print("Parent selection failed. Stopping.")
            break

        print(f"\n--- Top Metaprompt of Generation {gen + 1} ---")
        print(f"  Combined Score: {best_parent.get('combined_score', 'N/A'):.3f}")
        print(
            f"  (Breakdown: Aug: {best_parent.get('augmented_prompt_score', 'N/A'):.2f}, "
            f"Meta: {best_parent.get('metaprompt_score', 'N/A'):.2f}, "
            f"Intent: {best_parent.get('intent_preservation_score', 'N/A'):.2f})",
        )
        print(f"  Metaprompt: '{best_parent.get('metaprompt', 'N/A')}'")
        if "judgement" in best_parent:
            print(f"  Judge's Reasoning: {best_parent['judgement']}")

        # Store the augmented prompts data for the best parent
        best_parent_augmented_prompts = best_parent.get("augmented_prompts", [])

        # --- Generate and Evaluate Videos for Best Parent ---
        print("\n--- Generating and Evaluating Videos for Best Parent ---")
        video_evaluation_feedback = "No video evaluation performed."

        if ENABLE_VIDEO_FEEDBACK:
            if best_parent_augmented_prompts:
                video_generation_tasks = []
                video_pairs_for_evaluation = []

                for original_prompt_data in base_prompts:
                    # Find the corresponding augmented prompt for this original prompt
                    augmented_prompt_item = next(
                        (
                            item
                            for item in best_parent_augmented_prompts
                            if item["original_prompt"] == original_prompt_data["prompt"]
                        ),
                        None,
                    )

                    if augmented_prompt_item:
                        original_video_path, augmented_video_path, pair_dir = (
                            _get_video_paths(original_prompt_data)
                        )

                        # Task for generating original video (if it doesn't exist)
                        if not os.path.exists(original_video_path):
                            video_generation_tasks.append(
                                {
                                    "type": "original",
                                    "prompt": original_prompt_data["prompt"],
                                    "output_path": original_video_path,
                                    "image_path": original_prompt_data.get(
                                        "image_path",
                                    ),
                                },
                            )

                        # Task for generating augmented video
                        video_generation_tasks.append(
                            {
                                "type": "augmented",
                                "prompt": augmented_prompt_item["augmented_prompt"],
                                "output_path": augmented_video_path,
                                "image_path": original_prompt_data.get("image_path"),
                            },
                        )
                        video_pairs_for_evaluation.append(
                            {
                                "prompt": original_prompt_data["prompt"],
                                "video_a": original_video_path,
                                "video_b": augmented_video_path,
                                "image_path": original_prompt_data.get("image_path"),
                            },
                        )
                    else:
                        print(
                            f"    - No augmented prompt data for original prompt '{original_prompt_data['prompt']}', skipping video generation for this pair.",
                        )

                # Generate Videos in Parallel
                print("  - Generating videos in parallel...")
                if video_generation_tasks:
                    with ThreadPoolExecutor() as executor:
                        futures = []
                        for task in video_generation_tasks:
                            futures.append(
                                executor.submit(
                                    generate_videos.generate_single_video,
                                    client,
                                    task["prompt"],
                                    task["output_path"],
                                    task["image_path"],
                                ),
                            )

                        for future in as_completed(futures):
                            try:
                                success = future.result()
                                if not success:
                                    print("    - A video generation task failed.")
                            except Exception as exc:
                                print(
                                    f"    - Video generation task generated an exception: {exc}",
                                )
                else:
                    print("  - No videos to generate for best parent.")

                # Evaluate Videos in Parallel
                print("  - Evaluating generated video pairs in parallel...")
                if video_pairs_for_evaluation:
                    all_video_explanations = []
                    with ThreadPoolExecutor() as executor:
                        future_to_video_pair_eval = {
                            executor.submit(
                                evaluate_videos.process_video_pair,
                                client,
                                pair["prompt"],
                                pair["video_a"],
                                pair["video_b"],
                                evaluate_videos.SAMPLING_COUNT,
                                evaluate_videos.FLIP_ENABLED,
                                pair["image_path"],
                            ): pair
                            for pair in video_pairs_for_evaluation
                        }

                        for future in as_completed(future_to_video_pair_eval):
                            pair = future_to_video_pair_eval[future]
                            try:
                                video_eval_result = future.result()
                                if video_eval_result["status"] == "success":
                                    for individual_res in video_eval_result.get(
                                        "individual_results", [],
                                    ):
                                        all_video_explanations.append(
                                            f"Prompt: '{pair['prompt']}' - Video Comparison ({individual_res.get('better_video', 'N/A')} chosen): {individual_res.get('reasoning', 'No reason')}",
                                        )
                                else:
                                    all_video_explanations.append(
                                        f"Video evaluation skipped/failed for prompt '{pair['prompt']}': {video_eval_result['reason']}",
                                    )
                            except Exception as exc:
                                print(
                                    f"Video evaluation for prompt '{pair['prompt']}' generated an exception: {exc}",
                                )
                                all_video_explanations.append(
                                    f"Video evaluation exception for prompt '{pair['prompt']}': {exc}",
                                )

                    if all_video_explanations:
                        video_evaluation_feedback = "\n".join(all_video_explanations)
                    else:
                        video_evaluation_feedback = (
                            "No successful video evaluations for best parent."
                        )
                    print("  - Video Evaluation Feedback Collected.")
                else:
                    video_evaluation_feedback = (
                        "No video pairs to evaluate for best parent."
                    )
            else:
                video_evaluation_feedback = (
                    "No augmented prompts for best parent to generate videos."
                )
        else:
            video_evaluation_feedback = "Video feedback loop is disabled."

        all_generations_results.append(
            {
                "generation": gen + 1,
                "candidates": sorted(
                    evaluated_candidates,
                    key=lambda x: x.get("combined_score", 0),
                    reverse=True,
                ),
                "selected_parents": parents,
                "best_parent": best_parent,
                "best_parent_video_feedback": video_evaluation_feedback,
            },
        )

        new_population = []
        for p in parents:
            new_population.append(
                {
                    "metaprompt": p["metaprompt"],
                    "provenance": {
                        "type": "elitism",
                        "source_generation": gen + 1,
                        "original_provenance": p.get("provenance", {}),
                    },
                },
            )

        while len(new_population) < POPULATION_SIZE:
            if random.random() < 0.7:
                parent_to_mutate = random.choice(parents)
                print(
                    f"  - Performing Mutation on parent with score {parent_to_mutate.get('combined_score', 'N/A'):.3f}...",
                )
                mutation_prompt = f"""
                You are a Metaprompt Optimizer. Refine a metaprompt based on evaluation feedback.
                Remember that a veo metaprompt is a prompt that instructs an AI to generate augmented veo prompts.
                Parent Metaprompt: "{parent_to_mutate["metaprompt"]}"
                Augmented Prompt Feedback: "{parent_to_mutate.get("augmented_prompt_explanation", "N/A")}"
                Intent Preservation Feedback: "{parent_to_mutate.get("intent_preservation_explanation", "N/A")}"
                Instructional Quality Feedback: "{parent_to_mutate.get("metaprompt_explanation", "N/A")}"
                Video Evaluation Feedback for Best Parent: "{video_evaluation_feedback}" # Pass video feedback
                Generate one new, improved metaprompt that fixes weaknesses and enhances strengths, considering all sets of feedback.
                Always keep in mind the official veo prompting guide: {get_veo_prompting_guide()}
                Output only the new metaprompt text. Nothing else.
                """
                mutated = generate_with_gemini(client, mutation_prompt)
                new_population.append(
                    {
                        "metaprompt": mutated
                        if mutated
                        else parent_to_mutate["metaprompt"] + " (mutation failed)",
                        "provenance": {
                            "type": "mutation",
                            "parent_metaprompt": parent_to_mutate["metaprompt"],
                            "parent_score": parent_to_mutate.get("combined_score"),
                        },
                    },
                )
            elif len(parents) > 1:
                p1, p2 = random.sample(parents, 2)
                print(
                    f"  - Performing Crossover between parents (Scores: {p1.get('combined_score', 'N/A'):.3f}, {p2.get('combined_score', 'N/A'):.3f})...",
                )
                crossover_prompt = f"""
                    You are a Metaprompt Optimizer. Combine the strengths of two metaprompts.
                    Remember that a veo metaprompt is a prompt that instructs an AI to generate augmented veo prompts.
                    Metaprompt A: "{p1["metaprompt"]}" (Augmented Prompt Feedback: "{p1.get("augmented_prompt_explanation", "N/A")}", Intent Preservation Feedback: "{p1.get("intent_preservation_explanation", "N/A")}", Instructional Feedback: "{p1.get("metaprompt_explanation", "N/A")}")
                    Metaprompt B: "{p2["metaprompt"]}" (Augmented Prompt Feedback: "{p2.get("augmented_prompt_explanation", "N/A")}", Intent Preservation Feedback: "{p2.get("intent_preservation_explanation", "N/A")}", Instructional Feedback: "{p2.get("metaprompt_explanation", "N/A")}")
                    Video Evaluation Feedback for Best Parent: "{video_evaluation_feedback}" # Pass video feedback
                    Generate a new, hybrid metaprompt merging the best qualities of both.
                    Always keep in mind the official veo prompting guide: {get_veo_prompting_guide()}
                    Output only the new metaprompt text. Nothing else.
                    """
                crossed = generate_with_gemini(client, crossover_prompt)
                new_population.append(
                    {
                        "metaprompt": crossed
                        if crossed
                        else p1["metaprompt"] + " (crossover failed)",
                        "provenance": {
                            "type": "crossover",
                            "parents": [
                                {
                                    "metaprompt": p1["metaprompt"],
                                    "score": p1.get("combined_score"),
                                },
                                {
                                    "metaprompt": p2["metaprompt"],
                                    "score": p2.get("combined_score"),
                                },
                            ],
                        },
                    },
                )
            else:
                parent_to_mutate = parents[0]
                mutated = generate_with_gemini(
                    client, f"Slightly vary this: {parent_to_mutate['metaprompt']}",
                )
                new_population.append(
                    {
                        "metaprompt": mutated
                        if mutated
                        else parent_to_mutate["metaprompt"] + " (mutation failed)",
                        "provenance": {
                            "type": "mutation",
                            "parent_metaprompt": parent_to_mutate["metaprompt"],
                            "parent_score": parent_to_mutate.get("combined_score"),
                        },
                    },
                )

        population = new_population

    print("\n" + "=" * 80)
    print("### OPTIMIZATION COMPLETE ###")
    print("=" * 80)

    if all_generations_results:
        final_best = all_generations_results[-1]["best_parent"]
        print(
            f"Final Best Metaprompt (Combined Score: {final_best.get('combined_score', 'N/A'):.3f}):",
        )
        print(
            f"  (Breakdown: Aug: {final_best.get('augmented_prompt_score', 'N/A'):.2f}, "
            f"Meta: {final_best.get('metaprompt_score', 'N/A'):.2f}, "
            f"Intent: {final_best.get('intent_preservation_score', 'N/A'):.2f})",
        )
        print(final_best.get("metaprompt"))

        with open("optimized_metaprompt.py", "w") as f:
            f.write(
                f'optimized_metaprompt = """{final_best.get("metaprompt", "")}"""\n',
            )
        print("\nSaved best metaprompt to 'optimized_metaprompt.py'")

        with open("optimization_history.json", "w") as f:
            json.dump(all_generations_results, f, indent=2)
        print("Saved generation history to 'optimization_history.json'")
    else:
        print("Optimization did not produce any valid results.")


if __name__ == "__main__":
    main()
