# -*- coding: utf-8 -*-
"""
Main pipeline script to run the entire VEO Prompt Wizard workflow.
"""

import argparse

try:
    from . import prompt_optimizer
    from . import generate_prompts
    from . import generate_videos
    from . import evaluate_videos
except ImportError:
    import prompt_optimizer
    import generate_prompts
    import generate_videos
    import evaluate_videos


def main():
    """
    Runs the full pipeline:
    1. Optimizes the metaprompt.
    2. Generates augmented prompts.
    3. Generates videos from the prompts.
    4. Evaluates the generated video pairs.
    """
    parser = argparse.ArgumentParser(description="Run complete VEO Prompt Optimization Pipeline.")
    parser.add_argument("--skip-optimizer", action="store_true", help="Skip genetic prompt optimizer step.")
    parser.add_argument("--skip-videos", action="store_true", help="Skip video generation step.")
    parser.add_argument("--skip-evaluation", action="store_true", help="Skip video evaluation step.")
    args, _ = parser.parse_known_args()

    print("\n" + "="*80)
    print("### VEO PROMPT WIZARD PIPELINE STARTING ###")
    print("="*80)

    try:
        # Step 1: Run the prompt optimizer
        if not args.skip_optimizer:
            print("\n--- STEP 1: Running Prompt Optimizer ---")
            prompt_optimizer.main()
            print("--- STEP 1: Prompt Optimizer Complete ---")
        else:
            print("\n--- STEP 1: Skipped Prompt Optimizer ---")

        # Step 2: Generate augmented prompts
        print("\n--- STEP 2: Generating Augmented Prompts ---")
        generate_prompts.main()
        print("--- STEP 2: Augmented Prompts Generation Complete ---")

        # Step 3: Generate videos
        if not args.skip_videos:
            print("\n--- STEP 3: Generating Videos ---")
            generate_videos.main()
            print("--- STEP 3: Video Generation Complete ---")
        else:
            print("\n--- STEP 3: Skipped Video Generation ---")

        # Step 4: Evaluate videos
        if not args.skip_videos and not args.skip_evaluation:
            print("\n--- STEP 4: Evaluating Videos ---")
            evaluate_videos.main()
            print("--- STEP 4: Video Evaluation Complete ---")
        else:
            print("\n--- STEP 4: Skipped Video Evaluation ---")

    except Exception as e:
        print(f"\n\nPIPELINE FAILED: An error occurred: {e}")
        raise e

    print("\n" + "="*80)
    print("### VEO PROMPT WIZARD PIPELINE COMPLETED SUCCESSFULLY ###")
    print("="*80)


if __name__ == "__main__":
    main()
