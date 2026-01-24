# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging
import os

from extend_video.extend_image_generator import generate_scene_from_video
from extend_video.extend_video_generator import generate_video_from_last_frame
from image_generator import generate_images_and_select_best
from scene_prompts import scene2
from video_generator import generate_video_from_best_image

import config

# --- CONFIGURATION ---
# Set the path to the directory containing your input images.
IMAGE_LOCATION = config.INPUT_DIR
# Set the desired scenario or prompt for the generation.
SCENARIO = scene2
VIDEO_FILE = config.VIDEO_FILE_PATH
CONTEXT_IMAGE = config.CONTEXT_IMAGE
EXTENDED_VIDEO_FILE_PATH = config.EXTENDED_VIDEO_FILE_PATH

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def run_full_workflow(image_location: str, scenario: str):
    """Runs the full image and video generation workflow based on configured variables."""
    try:
        logger.info(f"Starting workflow for scenario: '{scenario}'")
        logger.info(f"Using images from: {image_location}")

        # Validate inputs
        if not os.path.isdir(image_location):
            logger.error(
                f"The provided image location is not a valid directory: {image_location}",
            )
            return

        image_files = [
            os.path.join(image_location, f)
            for f in os.listdir(image_location)
            if os.path.isfile(os.path.join(image_location, f))
        ]

        if not image_files:
            logger.error(f"No image files found in the directory: {image_location}")
            return

        if not scenario.strip():
            logger.error("The scenario (prompt) cannot be empty.")
            return

        # 1. Generate images and select the best one
        logger.info("Step 1: Generating images and selecting the best candidate...")
        output_path, best_image_path, _ = generate_images_and_select_best(
            image_files,
            scenario,
        )
        logger.info(f"Best image selected: {best_image_path}")
        logger.info(f"Generated assets stored in: {output_path}")

        # 2. Generate video from the best image
        logger.info("Step 2: Generating video from the best image...")
        video_path = generate_video_from_best_image(output_path, best_image_path)

        if video_path:
            logger.info(f"Successfully generated video: {video_path}")
            print(f"\nWorkflow complete. Video saved at: {video_path}")
        else:
            logger.error("Video generation failed.")
            print("\nWorkflow failed during video generation.")

    except Exception as e:
        logger.error(f"An error occurred during the workflow: {e}", exc_info=True)
        print(f"\nAn error occurred: {e}")


def run_extend_video_workflow(
    video_path: str,
    context_image_path: str,
    scenario: str,
    output_video_path: str,
):
    """Runs the full workflow to extend a video with a new scene, using a
    context image for character consistency.
    """
    try:
        logger.info(f"Starting video extension workflow for scenario: '{scenario}'")
        logger.info(f"Using video: {video_path}")
        logger.info(f"Using context image: {context_image_path}")

        # --- Input Validation ---
        if not os.path.isfile(video_path):
            logger.error(f"The provided video path is not a valid file: {video_path}")
            print(f"Error: Video not found at {video_path}")
            return

        if not os.path.isfile(context_image_path):
            logger.error(
                f"The provided context image path is not a valid file: {context_image_path}",
            )
            print(f"Error: Context image not found at {context_image_path}")
            return

        if not scenario.strip():
            logger.error("The scenario (prompt) cannot be empty.")
            print("Error: The scenario prompt cannot be empty.")
            return

        # 1. Generate a new scene image based on video context and a character image
        logger.info("Step 1: Generating a new scene image from video context...")
        (
            output_path,
            outpainted_image_path,
            character_description,
            best_scene_description,
        ) = generate_scene_from_video(
            video_path=video_path,
            context_image_path=context_image_path,
            user_prompt=scenario,
        )
        logger.info(f"New scene image generated: {outpainted_image_path}")
        logger.info(f"Generated assets stored in: {output_path}")
        logger.info(
            f"Generated character_description prompt is: {character_description}",
        )
        logger.info(
            f"Generated best_scene_description prompt is: {best_scene_description}",
        )

        # 2. Generate a final video from the newly created scene image
        logger.info("Step 2: Generating final video from the new scene image...")
        final_video_path = generate_video_from_last_frame(
            output_path=output_video_path,
            last_frame_path=outpainted_image_path,
            character_image_path=context_image_path,
            next_scene_prompt=scenario,
            character_description=character_description,
            best_scene_description=best_scene_description,
        )

        if final_video_path:
            logger.info(f"Successfully generated final video: {final_video_path}")
            print(f"\nWorkflow complete. 🎬 Video saved at: {final_video_path}")
        else:
            logger.error("Final video generation failed.")
            print("\nWorkflow failed during final video generation.")

    except Exception as e:
        logger.error(f"An error occurred during the workflow: {e}", exc_info=True)
        print(f"\nAn unexpected error occurred: {e}")


if __name__ == "__main__":
    # run_full_workflow(IMAGE_LOCATION, SCENARIO)
    # --- 2. Call the Extend video Workflow  ---
    run_extend_video_workflow(
        video_path=VIDEO_FILE,
        context_image_path=CONTEXT_IMAGE,
        scenario=SCENARIO,
        output_video_path=EXTENDED_VIDEO_FILE_PATH,
    )
