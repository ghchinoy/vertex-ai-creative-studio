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

import os
import time

from google import genai
from google.genai import types as genai_types
from PIL import Image

import config
from prompts import EXTEND_VIDEO_PROMPT


def initialize_clients():
    """Initializes and returns clients for Gemini and VEO, which are used
    for prompt generation and video generation respectively.
    """
    gemini_client = genai.Client(
        vertexai=True,
        project=config.PROJECT_ID,
        location=config.GEMINI_LOCATION,
    )
    veo_client = genai.Client(
        vertexai=True,
        project=config.PROJECT_ID,
        location=config.VEO_LOCATION,
    )
    return gemini_client, veo_client


def generate_video(
    gemini_client,
    veo_client,
    image_path,
    context_image_path,
    output_dir,
    next_scene_prompt,
    character_description,
    best_scene_description,
):
    """Generates a video by first creating a detailed prompt with Gemini and
    then generating the video with Veo using multiple references.
    """
    try:
        print("image_path ---->", image_path)
        # --- Prepare Image Objects ---
        scene_image = Image.open(image_path)
        character_image = Image.open(context_image_path)
        image_filename = os.path.basename(image_path)
        width, height = scene_image.size
        aspect_ratio = "9:16" if height > width else "16:9"

        # ==============================================================================
        # STEP 1: GENERATE THE CINEMATIC PROMPT USING YOUR MASTER PROMPT
        # ==============================================================================

        # Assemble your "director's notes" with the specific details for this task.
        user_data_for_prompt = f"""
        **Input 1: The Character Description (The "Who").**
        "{character_description}"

        **Input 2: The Scene Description (The "Where" & "Starting Pose").**
        "{best_scene_description}"

        **Input 3: The User's Prompt (The "Next Action").**
        "{next_scene_prompt}"
        """

        # Now, give Gemini the instruction manual (EXTEND_VIDEO_PROMPT) AND your notes.
        print("Generating a cinematic prompt with Gemini...")
        prompt_generation_response = gemini_client.models.generate_content(
            model=config.MULTIMODAL_MODEL_NAME,
            # The contents are the instructions, followed by the specific data.
            contents=[EXTEND_VIDEO_PROMPT, user_data_for_prompt],
        )

        video_prompt = prompt_generation_response.text.strip()
        print(f"✅ Cinematic Prompt Generated:\n---\n{video_prompt}\n---")

        # ==============================================================================
        # STEP 2: GENERATE THE VIDEO USING THE NEW PROMPT AND REFERENCE IMAGES
        # ==============================================================================

        print("Generating video with Veo...")

        print("scene_image ---->", scene_image)
        input_image = genai_types.Image.from_file(location=image_path)
        operation = veo_client.models.generate_videos(
            model=config.VEO_MODEL_NAME,
            prompt=video_prompt,
            image=input_image,
            config=genai_types.GenerateVideosConfig(
                duration_seconds=8,
                aspect_ratio=aspect_ratio,
                number_of_videos=1,
                enhance_prompt=True,
                person_generation="allow_adult",
            ),
        )

        while not operation.done:
            print("Video generation in progress... please wait.")
            time.sleep(10)
            operation = veo_client.operations.get(operation)

        if operation.error:
            print(f"❌ Error generating video: {operation.error}")
            return None

        video_data = operation.response.generated_videos[0].video.video_bytes
        video_filename = f"{os.path.splitext(image_filename)[0]}_extended.mp4"
        video_path = os.path.join(output_dir, video_filename)

        with open(video_path, "wb") as f:
            f.write(video_data)

        print(f"✅ Video successfully saved to: {video_path}")
        return video_path

    except Exception as e:
        print(f"An unexpected error occurred in generate_video: {e}")
        return None


def generate_video_from_last_frame(
    output_path: str,
    last_frame_path: str,
    character_image_path: str,
    next_scene_prompt: str,
    character_description: str,
    best_scene_description: str,
) -> str | None:
    """Generates a single video from the selected best image. This is the final
    step in the workflow, creating the video from the outpainted image.
    """
    gemini_client, veo_client = initialize_clients()
    os.makedirs(output_path, exist_ok=True)

    video_path = generate_video(
        gemini_client,
        veo_client,
        last_frame_path,
        character_image_path,
        output_path,
        next_scene_prompt,
        character_description,
        best_scene_description,
    )

    return video_path
