# -*- coding: utf-8 -*-
"""
Main script for the evolutionary optimization of VEO metaprompts.
"""

import json
import os
import random
import time
import argparse
from typing import List, Dict, Any, Tuple, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from google import genai

try:
    from . import config
    from . import evaluate_prompts
    from . import generate_videos
    from . import evaluate_videos
    from . import metaprompt as metaprompt_file
    from . import veo_prompt_eval_templates
except ImportError:
    import config
    import evaluate_prompts
    import generate_videos
    import evaluate_videos
    import metaprompt as metaprompt_file
    import veo_prompt_eval_templates


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


def get_veo_prompting_guide() -> str:
    """Returns the VEO prompting guide content."""
    guide_path = config.resolve_path("veo_guide.md")
    if guide_path.exists():
        with open(guide_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Enhance the prompt with cinematic lighting, camera movement, composition, subject detail, and high fidelity while preserving intent."


def generate_with_gemini(
    client: genai.Client,
    prompt_text: str,
    image_path: Optional[str] = None,
    response_schema: Optional[Dict[str, Any]] = None,
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
    if response_schema is not None:
        config_dict["response_mime_type"] = "application/json"
        config_dict["response_schema"] = response_schema

    cfg = genai.types.GenerateContentConfig(**config_dict)
    try:
        response = _generate_content_with_retry(client, model=model, contents=contents, config=cfg)
        return response.text
    except Exception as e:
        print(f"  - Gemini API call failed: {e}")
        return ""


def generate_initial_population(client: genai.Client, base_metaprompt: str, size: int) -> List[Dict[str, Any]]:
    """Generates the initial population of metaprompts as dictionaries with provenance."""
    print("--- Generating Initial Metaprompt Population ---")
    population = [{'metaprompt': base_metaprompt, 'provenance': {'type': 'initial_base'}}]
    
    if size <= 1:
        return population

    variation_prompt = f"""
    You are an expert prompt engineer. Based on the following base metaprompt, generate {size - 1} diverse, highly effective metaprompt variations.
    Each variation must instruct an AI model on how to augment a simple user prompt into a high-fidelity cinematic video prompt for Google Veo.
    Incorporate instructions on:
    - Cinematic camera motion and angles
    - Atmospheric lighting and color grading
    - Detailed subject and environment descriptions
    - Strict preservation of original user intent
    - Avoiding unwanted modifications or minors

    Base Metaprompt:
    "{base_metaprompt}"

    Return a JSON list of strings containing exactly {size - 1} variations.
    """
    
    array_schema = {"type": "ARRAY", "items": {"type": "STRING"}, "minItems": size - 1, "maxItems": size - 1}
    response_text = generate_with_gemini(client, variation_prompt, response_schema=array_schema)
    
    variations = []
    if response_text:
        try:
            variations = json.loads(response_text)
            print(f"Generated {len(variations)} initial variations.")
        except json.JSONDecodeError:
            print("  - Notice: Response was not direct JSON. Extracting line by line.")
            for line in response_text.splitlines():
                cleaned = line.strip().strip('"-*0123456789.[] ,')
                if len(cleaned) > 15:
                    variations.append(cleaned)

    fallback_templates = [
        "Rewrite the following prompt to add vivid visual detail, cinematic camera movement, and realistic lighting while strictly preserving original intent.",
        "Expand this prompt into a rich, photorealistic scene with specific camera angles, time of day, atmosphere, and high-fidelity motion without altering the core subjects.",
        "Act as a professional cinematographer. Transform this prompt into an award-winning video description, detailing camera lenses, textures, and fluid motion while keeping all original constraints intact.",
        "Augment the prompt by adding professional cinematography details: 4k resolution feel, lighting mood, depth of field, and natural action dynamics, retaining all initial elements.",
        "Enhance the following prompt with expressive motion, detailed textures, ambient lighting, and compositional depth for generative video, ensuring complete fidelity to the original idea.",
    ]

    while len(variations) < (size - 1):
        idx = len(variations) % len(fallback_templates)
        variations.append(fallback_templates[idx] + f" ({base_metaprompt})")

    for var in variations[:size - 1]:
        population.append({'metaprompt': var, 'provenance': {'type': 'initial_variation'}})

    return population[:size]


def _get_video_paths(prompt_data: Dict[str, Any], output_dir: str = "video_pairs") -> Tuple[str, str, str]:
    """Generates standardized video paths for original and augmented prompts."""
    if prompt_data.get("image_path"):
        base_name = os.path.splitext(os.path.basename(prompt_data["image_path"]))[0]
    else:
        sanitized_name = "".join(c for c in prompt_data["prompt"] if c.isalnum() or c in " _-").rstrip()
        base_name = f"text_{sanitized_name.replace(' ', '_').lower()[:30]}"
    
    pair_dir = os.path.join(output_dir, base_name)
    os.makedirs(pair_dir, exist_ok=True)
    
    original_video_path = os.path.join(pair_dir, "original.mp4")
    augmented_video_path = os.path.join(pair_dir, "augmented.mp4")
    
    return original_video_path, augmented_video_path, pair_dir


def get_metaprompt_fitness(
    client: genai.Client,
    candidate_metaprompt: str,
    base_prompts: List[Dict[str, Any]],
    sampling_count: int = 1
) -> Dict[str, Any]:
    """
    Calculates the fitness of a single metaprompt by evaluating its instructional
    quality, the effectiveness of the prompts it generates, and its ability
    to preserve the original user intent.
    """
    print(f"\n--- Evaluating Metaprompt ---\n'{candidate_metaprompt[:100]}...'")
    
    try:
        # Step 1: Direct Metaprompt Evaluation
        print("  - Evaluating metaprompt instructional quality...")
        meta_summary, meta_matrix = evaluate_prompts.evaluate_pointwise_batch(
            prompts_data=[{"metaprompt": candidate_metaprompt}],
            metric_name="metaprompt_effectiveness",
            metric_template=veo_prompt_eval_templates.METAPROMPT_EFFECTIVENESS_TEMPLATE,
            experiment="metaprompt-quality-check",
            sampling_count=sampling_count
        )
        metaprompt_score = meta_summary.get("metaprompt_effectiveness/mean", 0.0)
        metaprompt_explanation = (
            meta_matrix['metaprompt_effectiveness/explanation'].iloc[0]
            if not meta_matrix.empty and 'metaprompt_effectiveness/explanation' in meta_matrix
            else "Evaluation completed"
        )
        print(f"  - Instructional Quality Score: {metaprompt_score:.3f}")

        # Step 2: Generate Augmented Prompts
        print("  - Generating augmented prompts...")
        augmented_prompts_data = []
        for item in base_prompts:
            original_prompt = item['prompt']
            image_path = item.get('image_path')
            
            full_prompt = f"{candidate_metaprompt}\n\nOriginal Prompt: {original_prompt}\n\nYour output should be solely the augmented prompt text, nothing else."
            augmented_prompt = generate_with_gemini(client, full_prompt, image_path=image_path)
            
            if augmented_prompt:
                augmented_prompts_data.append({
                    "original_prompt": original_prompt,
                    "augmented_prompt": augmented_prompt.strip(),
                    "image_path": image_path
                })
            else:
                print(f"  - Failed to generate augmented prompt for '{original_prompt}'")
        
        # Step 3: Evaluate Augmented Prompts
        avg_effectiveness_score = 0.0
        aggregated_effectiveness_explanation = "No prompts to evaluate."
        avg_intent_score = 0.0
        aggregated_intent_explanation = "No prompts to evaluate."

        if augmented_prompts_data:
            has_images = any(item.get('image_path') for item in base_prompts)

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
                sampling_count=sampling_count
            )
            avg_effectiveness_score = eff_summary.get("veo_effectiveness/mean", 0.0)
            if not eff_matrix.empty and 'veo_effectiveness/explanation' in eff_matrix:
                aggregated_effectiveness_explanation = " | ".join(eff_matrix['veo_effectiveness/explanation'].dropna().tolist())
            print(f"  - Avg Effectiveness Score: {avg_effectiveness_score:.3f}")

            print("  - Evaluating augmented prompts for intent preservation...")
            intent_summary, intent_matrix = evaluate_prompts.evaluate_pointwise_batch(
                prompts_data=augmented_prompts_data,
                metric_name="intent_preservation",
                metric_template=intent_template,
                experiment="optimizer-intent-check",
                sampling_count=sampling_count
            )
            avg_intent_score = intent_summary.get("intent_preservation/mean", 0.0)
            if not intent_matrix.empty and 'intent_preservation/explanation' in intent_matrix:
                aggregated_intent_explanation = " | ".join(intent_matrix['intent_preservation/explanation'].dropna().tolist())
            print(f"  - Avg Intent Preservation Score: {avg_intent_score:.3f}")

        return {
            "augmented_prompt_score": avg_effectiveness_score,
            "augmented_prompt_explanation": aggregated_effectiveness_explanation,
            "intent_preservation_score": avg_intent_score,
            "intent_preservation_explanation": aggregated_intent_explanation,
            "metaprompt_score": metaprompt_score,
            "metaprompt_explanation": metaprompt_explanation,
            "augmented_prompts": augmented_prompts_data
        }
    except Exception as e:
        print(f"  - Error calculating metaprompt fitness: {e}")
        return {
            "augmented_prompt_score": 0.0,
            "augmented_prompt_explanation": f"Evaluation error: {e}",
            "intent_preservation_score": 0.0,
            "intent_preservation_explanation": f"Evaluation error: {e}",
            "metaprompt_score": 0.0,
            "metaprompt_explanation": f"Evaluation error: {e}",
            "augmented_prompts": []
        }


def _get_selection_from_gemini(client: genai.Client, candidates: List[Dict[str, Any]], top_k: int) -> Dict[str, Any]:
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
                        "reasoning": {"type": "STRING"}
                    },
                    "required": ["rank", "metaprompt", "reasoning"]
                },
                "minItems": top_k,
                "maxItems": top_k
            },
            "best_parent": {
                "type": "OBJECT",
                "properties": {
                    "metaprompt": {"type": "STRING"},
                    "reasoning": {"type": "STRING"}
                },
                "required": ["metaprompt", "reasoning"]
            }
        },
        "required": ["ranked_parents", "best_parent"]
    }

    candidates_text = "\n\n".join([
        (f"Metaprompt: \"{c['metaprompt']}\"\n"
         f"  - Combined Score: {c.get('combined_score', 0.0):.3f}\n"
         f"  - Augmented Prompt Score: {c.get('augmented_prompt_score', 0.0):.3f}\n"
         f"  - Intent Preservation Score: {c.get('intent_preservation_score', 0.0):.3f}\n"
         f"  - Instructional Quality Score: {c.get('metaprompt_score', 0.0):.3f}\n"
         f"  - Augmented Prompt Feedback: \"{c.get('augmented_prompt_explanation', 'N/A')}\"\n"
         f"  - Intent Preservation Feedback: \"{c.get('intent_preservation_explanation', 'N/A')}\"\n"
         f"  - Instructional Quality Feedback: \"{c.get('metaprompt_explanation', 'N/A')}\"")
        for c in candidates
    ])

    judge_prompt = f"""
    You are an expert judge in an evolutionary algorithm. Your task is to analyze {len(candidates)} candidate metaprompts that have achieved similar fitness scores and select the most promising ones for the next generation.

    **Primary Judging Criteria:**
    You must act as an expert evaluator. Use the following detailed rubric to guide your decision:
    1. Intent Preservation: Retaining every core subject, action, and concept.
    2. Detail Enrichment & Creativity: Adding specific, believable details without contradiction.
    3. Cinematic & Technical Language: Effective camera angles, composition, lighting, and movement.

    **Candidate Metaprompts to Evaluate:**
    {candidates_text}

    **Your Decision:**
    Rank the top {top_k} metaprompts and pick the overall best parent. Output valid JSON.
    """

    response_text = generate_with_gemini(client, judge_prompt, response_schema=selection_schema)
    try:
        return json.loads(response_text)
    except (json.JSONDecodeError, TypeError):
        print("  - Gemini judge returned non-JSON. Falling back to top candidates.")
        selected = candidates[:top_k] if len(candidates) >= top_k else candidates
        best = selected[0] if selected else {}
        return {
            "ranked_parents": [{"metaprompt": p["metaprompt"], "reasoning": "Fallback selection"} for p in selected],
            "best_parent": {"metaprompt": best.get("metaprompt", ""), "reasoning": "Fallback selection"}
        }


def select_parents(
    client: genai.Client,
    fitness_results: List[Dict[str, Any]],
    top_k: int = 2,
    aug_weight: float = 0.4,
    meta_weight: float = 0.3,
    intent_weight: float = 0.3
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Selects the top k parents from the fitness results, using a combined score
    and Gemini as a judge for ties.
    """
    if not fitness_results:
        return [], {}

    # Calculate combined score
    for r in fitness_results:
        aug_score = r.get('augmented_prompt_score', 0.0)
        meta_score = r.get('metaprompt_score', 0.0)
        intent_score = r.get('intent_preservation_score', 0.0)
        r['combined_score'] = (
            (aug_weight * aug_score) +
            (meta_weight * meta_score) +
            (intent_weight * intent_score)
        )

    fitness_results.sort(key=lambda x: x.get('combined_score', 0.0), reverse=True)
    print("\n--- Candidate Ranking (Combined Score) ---")
    for i, r in enumerate(fitness_results):
        print(f"{i+1}. Combined Score: {r['combined_score']:.3f} "
              f"(Aug: {r.get('augmented_prompt_score', 0):.2f}, "
              f"Meta: {r.get('metaprompt_score', 0):.2f}, "
              f"Intent: {r.get('intent_preservation_score', 0):.2f}) - "
              f"Metaprompt: '{r['metaprompt'][:80]}...'")

    use_judge = False
    if len(fitness_results) > top_k:
        score_at_cutoff = fitness_results[top_k - 1].get('combined_score', 0.0)
        score_after_cutoff = fitness_results[top_k].get('combined_score', 0.0)
        if abs(score_at_cutoff - score_after_cutoff) < 1e-9:
            use_judge = True
    
    if not use_judge and len(fitness_results) > 1:
        if abs(fitness_results[0].get('combined_score', 0.0) - fitness_results[1].get('combined_score', 0.0)) < 1e-9:
            use_judge = True

    if use_judge:
        print("\n  - Tie detected among top candidates based on combined score. Using Gemini as a judge.")
        cutoff_score = fitness_results[top_k - 1].get('combined_score', 0.0)
        candidates_to_judge = [r for r in fitness_results if r.get('combined_score', 0.0) >= (cutoff_score - 1e-9)]
        
        selection = _get_selection_from_gemini(client, candidates_to_judge, top_k)
        metaprompt_map = {r['metaprompt']: r for r in fitness_results}
        
        ranked_metaprompts = [p['metaprompt'] for p in selection.get('ranked_parents', [])]
        parents = [metaprompt_map[mp] for mp in ranked_metaprompts if mp in metaprompt_map]
        
        if not parents:
            parents = fitness_results[:top_k]

        best_parent_metaprompt = selection.get('best_parent', {}).get('metaprompt')
        best_parent = metaprompt_map.get(best_parent_metaprompt) or parents[0]
        if 'reasoning' in selection.get('best_parent', {}):
            best_parent['judgement'] = selection['best_parent']['reasoning']
    else:
        print("\n  - Selecting top parents based on combined scores.")
        parents = fitness_results[:top_k]
        best_parent = parents[0] if parents else {}

    return parents, best_parent


def main():
    """Main evolutionary loop with CLI argument support."""
    parser = argparse.ArgumentParser(description="Run Evolutionary Optimization for VEO Metaprompts.")
    parser.add_argument("--generations", type=int, default=config.NUM_GENERATIONS, help="Number of GA generations.")
    parser.add_argument("--population-size", type=int, default=config.POPULATION_SIZE, help="Population size.")
    parser.add_argument("--top-k", type=int, default=config.TOP_K_SELECTION, help="Number of elite parents to select.")
    parser.add_argument("--enable-video-feedback", action="store_true", default=config.ENABLE_VIDEO_FEEDBACK, help="Enable video feedback loop.")
    parser.add_argument("--prompts", default="original_prompts.json", help="Path to base prompts JSON file.")
    parser.add_argument("--output-metaprompt", default="optimized_metaprompt.py", help="Output file for best metaprompt.")
    parser.add_argument("--history", default="optimization_history.json", help="Output file for generation history.")
    args, _ = parser.parse_known_args()

    client = get_genai_client()
    config.init_vertexai()
    
    resolved_prompts_file = config.resolve_path(args.prompts)
    try:
        with open(resolved_prompts_file, 'r', encoding="utf-8") as f:
            original_prompts_data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Error loading or parsing '{resolved_prompts_file}': {e}. Exiting.")
        return

    base_prompts = [
        item for item in original_prompts_data
        if isinstance(item, dict) and 'prompt' in item
    ]

    if not base_prompts:
        print(f"No valid prompts found in '{resolved_prompts_file}'. Exiting.")
        return

    population = generate_initial_population(client, metaprompt_file.original_metaprompt, args.population_size)
    all_generations_results = []

    for gen in range(args.generations):
        print("\n" + "="*80)
        print(f"### STARTING GENERATION {gen+1}/{args.generations} ###")
        print("="*80)
        
        evaluated_candidates = []
        with ThreadPoolExecutor(max_workers=min(len(population), 8)) as executor:
            future_to_candidate = {
                executor.submit(get_metaprompt_fitness, client, candidate['metaprompt'], base_prompts, config.SAMPLING_COUNT): candidate
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
                    print(f"Candidate evaluation generated an exception: {exc}")
                    candidate.update({
                        "augmented_prompt_score": 0.0,
                        "metaprompt_score": 0.0,
                        "intent_preservation_score": 0.0,
                        "augmented_prompts": []
                    })
                    evaluated_candidates.append(candidate)

        if not evaluated_candidates:
            print("No metaprompts were evaluated. Stopping.")
            break
            
        parents, best_parent = select_parents(
            client,
            evaluated_candidates,
            top_k=args.top_k,
            aug_weight=config.AUGMENTED_PROMPT_SCORE_WEIGHT,
            meta_weight=config.METAPROMPT_SCORE_WEIGHT,
            intent_weight=config.INTENT_PRESERVATION_SCORE_WEIGHT
        )

        if not parents:
            print("Parent selection failed. Stopping.")
            break
        
        print(f"\n--- Top Metaprompt of Generation {gen+1} ---")
        print(f"  Combined Score: {best_parent.get('combined_score', 0.0):.3f}")
        print(f"  (Breakdown: Aug: {best_parent.get('augmented_prompt_score', 0.0):.2f}, "
              f"Meta: {best_parent.get('metaprompt_score', 0.0):.2f}, "
              f"Intent: {best_parent.get('intent_preservation_score', 0.0):.2f})")
        print(f"  Metaprompt: '{best_parent.get('metaprompt', 'N/A')}'")
        if 'judgement' in best_parent:
            print(f"  Judge's Reasoning: {best_parent['judgement']}")
        
        video_evaluation_feedback = "Video feedback loop disabled."
        if args.enable_video_feedback and best_parent.get('augmented_prompts'):
            print("\n--- Generating and Evaluating Videos for Best Parent ---")
            video_generation_tasks = []
            video_pairs_for_evaluation = []

            for original_prompt_data in base_prompts:
                augmented_prompt_item = next(
                    (item for item in best_parent['augmented_prompts'] if item['original_prompt'] == original_prompt_data['prompt']),
                    None
                )
                if augmented_prompt_item:
                    orig_v_path, aug_v_path, pair_dir = _get_video_paths(original_prompt_data)
                    if not os.path.exists(orig_v_path):
                        video_generation_tasks.append({
                            "prompt": original_prompt_data['prompt'],
                            "output_path": orig_v_path,
                            "image_path": original_prompt_data.get('image_path')
                        })
                    video_generation_tasks.append({
                        "prompt": augmented_prompt_item["augmented_prompt"],
                        "output_path": aug_v_path,
                        "image_path": original_prompt_data.get('image_path')
                    })
                    video_pairs_for_evaluation.append({
                        "prompt": original_prompt_data["prompt"],
                        "video_a": orig_v_path,
                        "video_b": aug_v_path,
                        "image_path": original_prompt_data.get('image_path')
                    })

            if video_generation_tasks:
                print("  - Generating videos in parallel...")
                with ThreadPoolExecutor(max_workers=config.VIDEO_GEN_MAX_WORKERS) as v_exec:
                    futures = [
                        v_exec.submit(generate_videos.generate_single_video, client, t["prompt"], t["output_path"], t["image_path"])
                        for t in video_generation_tasks
                    ]
                    for f in as_completed(futures):
                        try:
                            f.result()
                        except Exception as e:
                            print(f"Video generation error: {e}")

            if video_pairs_for_evaluation:
                print("  - Evaluating video pairs in parallel...")
                all_video_explanations = []
                with ThreadPoolExecutor(max_workers=config.VIDEO_EVAL_MAX_WORKERS) as e_exec:
                    future_to_eval = {
                        e_exec.submit(
                            evaluate_videos.process_video_pair,
                            client,
                            p["prompt"],
                            p["video_a"],
                            p["video_b"],
                            config.VIDEO_EVAL_SAMPLING_COUNT,
                            config.FLIP_ENABLED,
                            p["image_path"],
                        ): p
                        for p in video_pairs_for_evaluation
                    }
                    for f in as_completed(future_to_eval):
                        p = future_to_eval[f]
                        try:
                            res = f.result()
                            if res.get('status') == 'success':
                                for ind in res.get('individual_results', []):
                                    all_video_explanations.append(
                                        f"Prompt: '{p['prompt']}' - Result: {ind.get('better_video')} - {ind.get('reasoning')}"
                                    )
                        except Exception as e:
                            print(f"Video eval error for '{p['prompt']}': {e}")

                if all_video_explanations:
                    video_evaluation_feedback = "\n".join(all_video_explanations)

        all_generations_results.append({
            "generation": gen + 1,
            "candidates": sorted(evaluated_candidates, key=lambda x: x.get('combined_score', 0), reverse=True),
            "selected_parents": parents,
            "best_parent": best_parent,
            "best_parent_video_feedback": video_evaluation_feedback
        })
        
        # Build Next Generation
        new_population = []
        for p in parents:
            new_population.append({
                'metaprompt': p['metaprompt'],
                'provenance': {'type': 'elitism', 'source_generation': gen + 1}
            })

        guide_content = get_veo_prompting_guide()
        while len(new_population) < args.population_size:
            if random.random() < config.MUTATION_RATE:
                parent_to_mutate = random.choice(parents)
                mutation_prompt = f"""
                You are an Expert Prompt Engineer and Metaprompt Optimizer.
                Refine this metaprompt to better instruct an AI model to generate high-fidelity cinematic video prompts for Google Veo.
                Parent Metaprompt: "{parent_to_mutate['metaprompt']}"
                Augmented Prompt Feedback: "{parent_to_mutate.get('augmented_prompt_explanation', 'N/A')}"
                Intent Preservation Feedback: "{parent_to_mutate.get('intent_preservation_explanation', 'N/A')}"
                Instructional Quality Feedback: "{parent_to_mutate.get('metaprompt_explanation', 'N/A')}"
                Video Evaluation Feedback: "{video_evaluation_feedback}"

                Veo Prompting Guide Guidelines:
                {guide_content}

                Generate a single new, improved metaprompt that addresses feedback and elevates prompt richness.
                Output ONLY the new metaprompt text.
                """
                mutated = generate_with_gemini(client, mutation_prompt)
                new_population.append({
                    'metaprompt': mutated.strip() if mutated else parent_to_mutate['metaprompt'],
                    'provenance': {'type': 'mutation', 'parent_score': parent_to_mutate.get('combined_score')}
                })
            else:
                if len(parents) > 1:
                    p1, p2 = random.sample(parents, 2)
                    crossover_prompt = f"""
                    You are an Expert Metaprompt Optimizer. Combine the unique strengths of these two metaprompts.
                    Metaprompt A: "{p1['metaprompt']}"
                    Metaprompt B: "{p2['metaprompt']}"
                    Video Evaluation Feedback: "{video_evaluation_feedback}"

                    Veo Prompting Guide Guidelines:
                    {guide_content}

                    Generate a cohesive, hybrid metaprompt combining the best aspects of both.
                    Output ONLY the new metaprompt text.
                    """
                    crossed = generate_with_gemini(client, crossover_prompt)
                    new_population.append({
                        'metaprompt': crossed.strip() if crossed else p1['metaprompt'],
                        'provenance': {'type': 'crossover'}
                    })
                else:
                    parent_to_mutate = parents[0]
                    mutated = generate_with_gemini(client, f"Slightly improve and rephrase this metaprompt: {parent_to_mutate['metaprompt']}")
                    new_population.append({
                        'metaprompt': mutated.strip() if mutated else parent_to_mutate['metaprompt'],
                        'provenance': {'type': 'mutation'}
                    })

        population = new_population

    print("\n" + "="*80)
    print("### OPTIMIZATION COMPLETE ###")
    print("="*80)
    
    if all_generations_results:
        final_best = all_generations_results[-1]['best_parent']
        print(f"Final Best Metaprompt (Combined Score: {final_best.get('combined_score', 0.0):.3f}):")
        print(final_best.get('metaprompt'))
        
        out_meta_path = config.resolve_path(args.output_metaprompt)
        with open(out_meta_path, "w", encoding="utf-8") as f:
            f.write(f'optimized_metaprompt = """{final_best.get("metaprompt", "")}"""\n')
        print(f"\nSaved best metaprompt to '{out_meta_path}'")

        out_hist_path = config.resolve_path(args.history)
        with open(out_hist_path, "w", encoding="utf-8") as f:
            json.dump(all_generations_results, f, indent=2)
        print(f"Saved generation history to '{out_hist_path}'")


if __name__ == "__main__":
    main()
