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
from prompts import VEO_PROMPT


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


def generate_video(gemini_client, veo_client, image_path, output_dir):
    """Generates and saves a single video based on a reference image. This
    function uses Gemini to generate a creative prompt and then uses Veo to
    generate the video.
    """
    try:
        image_filename = os.path.basename(image_path)
        pil_image = Image.open(image_path)

        width, height = pil_image.size
        aspect_ratio = "9:16" if height > width else "16:9"

        video_prompt_response = gemini_client.models.generate_content(
            model=config.MULTIMODAL_MODEL_NAME,
            contents=[VEO_PROMPT, pil_image],
            config=genai_types.GenerateContentConfig(
                thinking_config=genai_types.ThinkingConfig(thinking_budget=-1),
            ),
        )
        video_prompt = video_prompt_response.text.strip()

        input_image = genai_types.Image.from_file(location=image_path)

        operation = veo_client.models.generate_videos(
            model=config.VEO_MODEL_NAME,
            prompt=video_prompt,
            config=genai_types.GenerateVideosConfig(
                duration_seconds=8,
                aspect_ratio=aspect_ratio,
                number_of_videos=1,
                enhance_prompt=True,
                person_generation="allow_adult",
            ),
            image=input_image,
        )

        while not operation.done:
            time.sleep(10)
            operation = veo_client.operations.get(operation)

        if operation.error:
            print(f"Error generating video: {operation.error}")
            return None

        video_data = operation.response.generated_videos[0].video.video_bytes
        video_filename = f"{os.path.splitext(image_filename)[0]}.mp4"
        video_path = os.path.join(output_dir, video_filename)

        with open(video_path, "wb") as f:
            f.write(video_data)

        return video_path

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return None


def generate_video_from_best_image(
    output_path: str,
    best_image_path: str,
) -> str | None:
    """Generates a single video from the selected best image. This is the final
    step in the workflow, creating the video from the outpainted image.
    """
    gemini_client, veo_client = initialize_clients()
    os.makedirs(output_path, exist_ok=True)

    video_path = generate_video(gemini_client, veo_client, best_image_path, output_path)

    return video_path
