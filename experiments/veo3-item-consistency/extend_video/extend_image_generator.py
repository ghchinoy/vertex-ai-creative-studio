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

import concurrent.futures
import os

from google import genai
from google.genai import types
from google.genai.types import GenerateContentConfig
from utils.outpainting import outpaint_image
from utils.schemas import BestFrameSelection, GeneratedPrompts, SceneAnalysis

import config

from .extract_frame import extract_last_frames, save_frames_to_temp

# Initialize clients
client = genai.Client(
    vertexai=True,
    project=config.PROJECT_ID,
    location=config.GEMINI_LOCATION,
)

edit_model = config.IMAGEN_MODEL_NAME
gemini_model = config.MULTIMODAL_MODEL_NAME


# --- HELPER FUNCTIONS ---


def _get_description_for_image(image_path: str) -> str:
    """Analyzes a single image to extract detailed character and/or machine
    profiles, then generates one unified natural language description.
    """
    model_name = gemini_model  # Using a specific model version

    # Step 1: Extract structured profiles
    profile_config = GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=SceneAnalysis.model_json_schema(),
        temperature=0.1,
    )
    profile_prompt_parts = [
        "You are a scene analyst. Profile any human subjects and any machines in the image. "
        "Extract a detailed, structured profile for each entity found into the provided JSON schema.",
        types.Part.from_bytes(
            data=types.Image.from_file(location=image_path).image_bytes,
            mime_type="image/png",
        ),
    ]
    profile_response = client.models.generate_content(
        model=model_name,
        contents=profile_prompt_parts,
        config=profile_config,
    )
    analysis = SceneAnalysis.model_validate_json(profile_response.text)

    # Step 2: Generate ONE description from the combined analysis
    description_config = GenerateContentConfig(temperature=0.1)
    description_prompt = f"""
    Based on the following structured JSON data, write a concise, natural language description suitable for an image generation model.
    Focus on the key physical traits of the character and the machine, describing them as a cohesive scene (e.g., "A man driving an orange forklift").

    JSON Profile:
    {analysis.model_dump_json(indent=2)}
    """
    description_response = client.models.generate_content(
        model=model_name,
        contents=[description_prompt],
        config=description_config,
    )
    return description_response.text.strip()


def _select_best_scene_frame(scene_descriptions: list[str], user_prompt: str) -> int:
    """Uses Gemini to analyze a list of frame descriptions and select the best one
    to serve as a starting point for the user's desired next scene.
    """
    model_name = gemini_model

    formatted_descriptions = "\n".join(
        [f"Frame {i}: {desc}" for i, desc in enumerate(scene_descriptions)],
    )

    selection_prompt = f"""
    You are an expert film editor's assistant. Your task is to choose the best
    single frame to serve as the starting point for the next action in a scene.

    **Goal for the next scene:**
    "{user_prompt}"

    **Available frames from the end of the previous clip:**
    {formatted_descriptions}

    **Instructions:**
    Review the available frames and the user's goal. Select the one frame that provides
    the most logical and visually appropriate starting pose and context. For example,
    if the goal is "turn and face the camera," a frame showing the person's back might be the best choice.

    Return your choice in the provided JSON format.
    """

    response = client.models.generate_content(
        model=model_name,
        contents=[selection_prompt],
        config=GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=BestFrameSelection.model_json_schema(),
            temperature=0.1,
        ),
    )

    selection = BestFrameSelection.model_validate_json(response.text)
    print(
        f"AI selected Frame {selection.best_frame_index}. Reason: {selection.reasoning}",
    )

    return selection.best_frame_index


def _generate_final_scene_prompt(
    character_description: str,
    scene_description: str,
    user_prompt: str,
) -> GeneratedPrompts:
    """Generates a detailed prompt by combining a character description,
    a scene context, and a new user command.
    """
    model_name = gemini_model
    config = GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=GeneratedPrompts.model_json_schema(),
        temperature=0.3,
    )

    meta_prompt = f"""
    You are an expert prompt engineer. Your task is to create a detailed, photorealistic prompt.

    **Primary Character Description (from a reference image):**
    {character_description}

    **Scene Context (from the selected best video frame):**
    {scene_description}

    **User's Desired Action/Scene:**
    {user_prompt}

    **Instructions:**
    1.  Create a single, coherent prompt that continues the action from the scene context, guided by the user's desired action.
    2.  The character in the prompt must match the Primary Character Description.
    3.  The final prompt should be suitable for guiding an outpainting or image editing model.
    4.  Add photography keywords like lens type (e.g., 50mm portrait lens), lighting (e.g., golden hour), and high-detail keywords.
    5.  Generate a standard negative prompt to avoid common artistic flaws.
    """

    response = client.models.generate_content(
        model=model_name,
        contents=[meta_prompt],
        config=config,
    )
    return GeneratedPrompts.model_validate_json(response.text)


# --- CORE WORKFLOW FUNCTION ---


def generate_scene_from_video(
    video_path: str,
    context_image_path: str,
    user_prompt: str,
) -> tuple[str, str, str]:
    """Analyzes video frames, selects the best one for context, and prepares it
    for the next step (e.g., outpainting) without generating a new image.
    """
    output_dir = config.OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    # STEP 1: Extract frames from the video and save them to a temporary folder.
    print("Extracting last frames from video...")
    last_frames = extract_last_frames(video_path, num_frames=4)
    if not last_frames:
        raise ValueError("Could not extract any frames from the video.")

    # Get the folder path where frames are saved, then build a list of full file paths.
    temp_folder = save_frames_to_temp(frames=last_frames)
    last_frame_paths = [
        os.path.join(temp_folder, f) for f in sorted(os.listdir(temp_folder))
    ]
    print(f"Frames saved to and read from: {temp_folder}")

    # STEP 2: Analyze the character image and all extracted frames to get their descriptions.
    print("Generating descriptions for character image and all frames...")
    character_description = _get_description_for_image(context_image_path)
    with concurrent.futures.ThreadPoolExecutor() as executor:
        scene_descriptions = list(
            executor.map(_get_description_for_image, last_frame_paths),
        )

    # STEP 3: Use AI to select the single best frame that provides context for the next action.
    print("AI is selecting the best frame for scene context...")
    best_frame_index = _select_best_scene_frame(
        scene_descriptions=scene_descriptions,
        user_prompt=user_prompt,
    )
    best_frame_path = last_frame_paths[best_frame_index]
    best_scene_description = scene_descriptions[best_frame_index]
    print(f"Selected '{best_frame_path}' as the best scene reference.")

    # STEP 4: Generate a guiding prompt for the next step (e.g., outpainting or video generation).
    print("Generating a guiding prompt for the next step...")
    generated_prompts = _generate_final_scene_prompt(
        character_description=character_description,
        scene_description=best_scene_description,
        user_prompt=user_prompt,
    )
    final_prompt = generated_prompts.prompt

    # --- SKIPPED: The image generation and selection steps are intentionally removed. ---

    # STEP 5: Proceed directly to the next step using the selected frame.
    print(f"Proceeding directly with the selected frame: {best_frame_path}")

    print("Outpainting selected frame...")
    outpainted_image_path = outpaint_image(best_frame_path, final_prompt)
    print(f"Outpainted image saved to: {outpainted_image_path}")

    # Return the path to the outpainted image and the path of the frame that was chosen.
    return (
        output_dir,
        outpainted_image_path,
        character_description,
        best_scene_description,
    )
