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

"""This module provides functions for interacting with the Gemini model.

It includes functions for generating content, improving prompts, and generating
thoughts for prompt improvement. It also uses the `tenacity` library to
provide automatic retries with exponential backoff for the Gemini API calls,
which makes the application more resilient to transient errors.
"""

from google.genai.types import (
    GenerateContentConfig,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from models.model_setup import ModelSetup
from models.prompts import (
    PROMPT_IMPROVEMENT_INSTRUCTIONS,
    PROMPT_IMPROVEMENT_PLANNING_INSTRUCTIONS,
)

client, model_id = ModelSetup.init()
MODEL_ID = model_id


@retry(
    wait=wait_exponential(
        multiplier=1,
        min=1,
        max=10,
    ),  # Exponential backoff (1s, 2s, 4s... up to 10s)
    stop=stop_after_attempt(3),  # Stop after 3 attempts
    retry=retry_if_exception_type(Exception),  # Retry on all exceptions
    reraise=True,  # re-raise the last exception if all retries fail
)
def gemini_generate_content(system_prompt: str = "", prompt: str = "") -> str:
    """Invokes the Gemini model to generate content.

    This function sends a prompt to the Gemini model and returns the generated
    content. It can also accept an optional system prompt to guide the model's
    behavior.

    Args:
        system_prompt: An optional system prompt to guide the model.
        prompt: The main prompt to send to the model.

    Returns:
        The generated content as a string.

    """
    try:
        if system_prompt:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
                config=GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_modalities=["TEXT"],
                ),
            )
        else:
            response = client.models.generate_content(
                model=MODEL_ID,
                contents=prompt,
                config=GenerateContentConfig(
                    response_modalities=["TEXT"],
                ),
            )
        # page_state.prompt_response = response.text
        print(f"success! {response.text}")
        return response.text
    except Exception as e:
        print(f"error: {e}")
        raise  # Re-raise the exception for tenacity to handle


@retry(
    wait=wait_exponential(
        multiplier=1,
        min=1,
        max=10,
    ),  # Exponential backoff (1s, 2s, 4s... up to 10s)
    stop=stop_after_attempt(3),  # Stop after 3 attempts
    retry=retry_if_exception_type(Exception),  # Retry on all exceptions
    reraise=True,  # re-raise the last exception if all retries fail
)
def gemini_improve_this_prompt(
    system_prompt: str = "",
    prompt: str = "",
    basic_instructions: str = "",
    plan: str = "",
) -> str:
    """Improves a prompt using the Gemini model.

    This function takes a prompt, an optional system prompt, basic instructions,
    and a plan, and then uses the Gemini model to generate an improved version
    of the prompt.

    Args:
        system_prompt: An optional system prompt to guide the model.
        prompt: The prompt to improve.
        basic_instructions: Basic instructions for the improvement.
        plan: The plan for improving the prompt.

    Returns:
        The improved prompt as a string.

    """
    improvement_prompt = PROMPT_IMPROVEMENT_INSTRUCTIONS.format(
        plan,
        f"{system_prompt} {prompt}",
        basic_instructions,
    )

    try:
        response = client.models.generate_content(
            model=MODEL_ID,
            contents=improvement_prompt,
            config=GenerateContentConfig(
                response_modalities=["TEXT"],
            ),
        )
        # page_state.prompt_response = response.text
        print(f"success! {response.text}")
        return response.text
    except Exception as e:
        print(f"error: {e}")
        raise  # Re-raise the exception for tenacity to handle


@retry(
    wait=wait_exponential(
        multiplier=1,
        min=1,
        max=10,
    ),  # Exponential backoff (1s, 2s, 4s... up to 10s)
    stop=stop_after_attempt(3),  # Stop after 3 attempts
    retry=retry_if_exception_type(Exception),  # Retry on all exceptions
    reraise=True,  # re-raise the last exception if all retries fail
)
def gemini_thinking_thoughts(
    system_prompt: str = "",
    prompt: str = "",
    prompt_improvement_instructions: str = "",
) -> str:
    """Generates a plan for improving a prompt using the Gemini model.

    This function takes a prompt, an optional system prompt, and prompt
    improvement instructions, and then uses the Gemini model to generate a plan
    for improving the prompt.

    Args:
        system_prompt: An optional system_prompt to guide the model.
        prompt: The prompt to improve.
        prompt_improvement_instructions: Instructions for the improvement.

    Returns:
        The plan for improving the prompt as a string.

    """
    planning_prompt = PROMPT_IMPROVEMENT_PLANNING_INSTRUCTIONS.format(
        f"{system_prompt} {prompt}",
        prompt_improvement_instructions,
    )

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=planning_prompt,
            config=GenerateContentConfig(
                response_modalities=["TEXT"],
            ),
        )
        # page_state.prompt_response = response.text
        print(f"success! {response.text}")
        return response.candidates[0].content.parts[0].text
    except Exception as e:
        print(f"error: {e}")
        raise  # Re-raise the exception for tenacity to handle
