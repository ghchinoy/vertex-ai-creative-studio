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
"""Model logic for guideline analysis."""

from pydantic import BaseModel

from config.default import Default
from models.gemini import client, generate_critique_questions, types

# Prompts from test/brandguard/samples.py
BAS_RUBRIC_GENERATION_PROMPT = """
Given a brand guideline with multiple criteria and additional free-text guidance, your task is to create a set of precise Yes/No questions to check for compliance. This is for a Brand Alignment Scorecard (BAS).

Generate a list of Yes/No questions based on both the brand criteria and the additional guidance provided.
Crucially, all questions must be phrased so that a "Yes" answer indicates compliance. For example, for a negative rule like "Avoid beaches", the question should be "Is the setting something other than a beach?".
The "answer" for each question must be "yes", as it represents the ground truth for compliance.

Your output must be a JSON object in the exact format shown in the example.

===
**EXAMPLE:**

**Brand Guideline Criteria to Enforce:**
- When a logo is present, it must be clearly visible and unobscured.
- The background should be simple and not distracting.
**Additional Guidance:**
Avoid showing any text other than the brand logo. Do not show the product in a beach setting.

**Answer:**
{{
  "qas": [
    {{
      "criterion_id": "cr-logo-visible",
      "question": "If a logo is present in the image, is it clearly visible and unobscured?",
      "justification": "This is a requirement from the brand guidelines. An image without a logo is not in violation, but if a logo exists, it must be visible.",
      "answer": "yes"
    }},
    {{
      "criterion_id": "cr-background-style",
      "question": "Is the background simple and not distracting?",
      "justification": "This is a requirement from the brand guidelines.",
      "answer": "yes"
    }},
    {{
      "criterion_id": "additional-guidance-text",
      "question": "Is the image free of any text other than the official brand logo?",
      "justification": "This is a requirement from the additional guidance. 'Yes' indicates compliance.",
      "answer": "yes"
    }},
    {{
      "criterion_id": "additional-guidance-setting",
      "question": "Is the product shown in a setting other than a beach?",
      "justification": "This is a requirement from the additional guidance. 'Yes' indicates compliance.",
      "answer": "yes"
    }}
  ]
}}
===

**BRAND GUIDELINE CRITERIA TO ENFORCE:**
{criteria}

**ADDITIONAL GUIDANCE (e.g., negative prompts):**
{additional_guidance}

**Answer:**
"""


DSG_RUBRIC_GENERATION_PROMPT = """
You are an expert quality assurance tester for AI-generated media.
Given a source prompt, your task is to create a set of precise Yes/No questions to check for two things:
1.  **Prompt Fidelity (DSG):** Is each key component of the source prompt present in the asset? This is for a Davidsonian Scene Graph (DSG) analysis.
2.  **General Quality (GQM):** Is the asset technically and aesthetically well-made, and free of common AI mistakes? This is for a General Quality & Mistakes (GQM) evaluation.

**Instructions:**

**Part 1: Prompt Fidelity Questions (DSG)**
- Analyze the source prompt and break it down into its key components.
- In the JSON output, create a "keywords" string where each component is enclosed in numbered brackets, like `{{1}}`[component]`.
- Generate multiple Yes/No questions for each identified component.

**Part 2: General Quality Questions (GQM)**
- Generate additional Yes/No questions that address the following general quality dimensions:
  - **Object Permanence & Consistency:** Do objects or characters maintain a consistent appearance?
  - **Plausibility & Realism:** Do interactions like lighting and shadows appear natural?
  - **Aesthetic Quality:** Is the asset free of obvious visual glitches, artifacts, or excessive blur?
  - **Natural Movement (for video):** Is movement fluid and not distorted?

**Formatting Rules:**
- All questions must be phrased so that a "Yes" answer indicates compliance or high quality.
- The "answer" for all questions must be "yes" as this reflects the ground truth of what was requested in the prompt and the expected level of quality.
- Your output must be a single JSON object in the exact format shown in the example.

===
**EXAMPLE:**

**Source Prompt:** A close-up of a luxurious gold watch with a leather strap on a man's wrist.

**Answer:**
{{
  "keywords": "A `{{1}}`[close-up] of a `{{2}}`[luxurious] `{{3}}`[gold] watch with a `{{4}}`[leather strap] on a `{{5}}`[man's wrist].",
  "qas": [
    {{
      "criterion_id": "prompt-component-1",
      "question": "Is the image a close-up shot?",
      "justification": "DSG: The source prompt explicitly states a 'close-up' (`{{1}}`).",
      "answer": "yes"
    }},
    {{
      "criterion_id": "prompt-component-3",
      "question": "Is the watch case made of gold?",
      "justification": "DSG: The source prompt explicitly states the watch is 'gold' (`{{3}}`).",
      "answer": "yes"
    }},
    {{
      "criterion_id": "prompt-component-5",
      "question": "Is the watch displayed on a man's wrist?",
      "justification": "DSG: The source prompt specifies a 'man's wrist' (`{{5}}`).",
      "answer": "yes"
    }},
    {{
      "criterion_id": "gqm-artifacts",
      "question": "Is the image free of noticeable visual artifacts, distortions, or glitches?",
      "justification": "GQM: Checks for general aesthetic quality and common AI generation errors.",
      "answer": "yes"
    }},
    {{
      "criterion_id": "gqm-lighting",
      "question": "Are the lighting and shadows on the watch and wrist plausible and consistent?",
      "justification": "GQM: Checks for physical realism and plausibility.",
      "answer": "yes"
    }}
  ]
}}
===

**Source Prompt:**
{source_prompt}

**Answer:**
"""


class QA(BaseModel):
    criterion_id: str
    question: str
    justification: str
    answer: str


class QAList(BaseModel):
    qas: list[QA]


def _generate_questions_from_prompt(
    prompt_template: str,
    image_uri: str | None = None,
    **kwargs,
) -> list[str]:
    """Helper to generate questions from a given prompt template."""
    cfg = Default()
    model_name = cfg.MODEL_ID
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=QAList.model_json_schema(),
        temperature=0.2,
    )
    prompt = prompt_template.format(**kwargs)

    if image_uri:
        prompt += "\n\n**REFERENCE IMAGE:**\nA reference image has been provided. Use this image to extract additional visual criteria (e.g., specific color shades, logo placement style, lighting mood) that should be enforced."

    contents = [prompt]
    if image_uri:
        contents.append(types.Part.from_uri(file_uri=image_uri, mime_type="image/png"))

    response = client.models.generate_content(
        model=model_name,
        contents=contents,
        config=config,
    )
    try:
        qa_list = QAList.model_validate_json(response.text)
        return [qa.question for qa in qa_list.qas]
    except Exception as e:
        print(f"Error parsing question generation response: {e}")
        print(f"Raw response: {response.text}")
        return []


def generate_dsg_gqm_questions(source_prompt: str) -> list[str]:
    """Generates DSG and GQM questions from a source prompt."""
    if not source_prompt:
        return []
    return _generate_questions_from_prompt(
        DSG_RUBRIC_GENERATION_PROMPT,
        source_prompt=source_prompt,
    )


def generate_bas_questions(
    prompt: str,
    additional_guidance: str,
    image_uri: str | None = None,
) -> list[str]:
    """Generates BAS questions from a prompt."""
    if not prompt:
        return []
    # Use the same prompt for both criteria and additional guidance for simplicity
    return _generate_questions_from_prompt(
        BAS_RUBRIC_GENERATION_PROMPT,
        criteria=prompt,
        additional_guidance=additional_guidance,
        image_uri=image_uri,
    )


def generate_guideline_criteria(
    prompt: str,
    additional_guidance: str,
    reference_image_uri: str | None = None,
) -> dict[str, list[str]]:
    """Generates a dictionary of critique questions based on a prompt."""
    if not prompt:
        return {}

    general_criteria = generate_critique_questions(prompt=prompt, image_descriptions=[])
    dsg_gqm_criteria = generate_dsg_gqm_questions(source_prompt=prompt)
    bas_criteria = generate_bas_questions(
        prompt=prompt,
        additional_guidance=additional_guidance,
        image_uri=reference_image_uri,
    )

    return {
        "General": general_criteria,
        "DSG/GQM": dsg_gqm_criteria,
        "Brand Alignment (BAS)": bas_criteria,
    }
