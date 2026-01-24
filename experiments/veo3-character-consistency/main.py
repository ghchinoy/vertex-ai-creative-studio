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

from image_generator import generate_images_and_select_best
from video_generator import generate_video_from_best_image

import config

# --- CONFIGURATION ---
# Set the path to the directory containing your input images.
IMAGE_LOCATION = config.INPUT_DIR
# Set the desired scenario or prompt for the generation.
SCENARIO = "a man wearing a spiderman outfit in the desert"

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


if __name__ == "__main__":
    run_full_workflow(IMAGE_LOCATION, SCENARIO)
