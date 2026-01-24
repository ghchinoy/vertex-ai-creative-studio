"""Main pipeline script to run the entire VEO Prompt Wizard workflow."""

import evaluate_videos
import generate_prompts
import generate_videos
import prompt_optimizer


def main():
    """Runs the full pipeline:
    1. Optimizes the metaprompt.
    2. Generates augmented prompts.
    3. Generates videos from the prompts.
    4. Evaluates the generated video pairs.
    """
    print("\n" + "=" * 80)
    print("### VEO PROMPT WIZARD PIPELINE STARTING ###")
    print("=" * 80)

    try:
        # Step 1: Run the prompt optimizer
        print("\n--- STEP 1: Running Prompt Optimizer ---")
        prompt_optimizer.main()
        print("--- STEP 1: Prompt Optimizer Complete ---")

        # Step 2: Generate augmented prompts
        print("\n--- STEP 2: Generating Augmented Prompts ---")
        generate_prompts.main()
        print("--- STEP 2: Augmented Prompts Generation Complete ---")

        # Step 3: Generate videos
        print("\n--- STEP 3: Generating Videos ---")
        generate_videos.main()
        print("--- STEP 3: Video Generation Complete ---")

        # Step 4: Evaluate videos
        print("\n--- STEP 4: Evaluating Videos ---")
        evaluate_videos.main()
        print("--- STEP 4: Video Evaluation Complete ---")

    except Exception as e:
        print(f"\n\nPIPELINE FAILED: An error occurred: {e}")
        raise e
        return

    print("\n" + "=" * 80)
    print("### VEO PROMPT WIZARD PIPELINE COMPLETED SUCCESSFULLY ###")
    print("=" * 80)


if __name__ == "__main__":
    main()
