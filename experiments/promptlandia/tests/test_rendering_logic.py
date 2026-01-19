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

import json
import os
import re

# --- Test Logic (without Pydantic) ---


def parse_evaluation_markdown(markdown_text: str) -> dict:
    """Parses the markdown output from the evaluation prompt into a dict
    that can be used for rendering.
    """
    sections = re.split(r"# Prompt analysis for ", markdown_text)
    parsed_data = {}

    for section in sections:
        if not section.strip():
            continue

        lines = section.strip().split("\n")
        category_name = lines[0].strip()
        content = "\n".join(lines[1:]).strip()

        json_matches = re.findall(r"```json\n(.*?)\n```", content, re.DOTALL)

        if "Issue not present in the prompt" in content or not json_matches:
            category_data = {
                "items": {"Issue Found": False},
                "details": {"Issue Found": "No issue was found for this category."},
                "explanation": "The model did not find any issues for this category.",
            }
        else:
            try:
                json_data = json.loads(json_matches[0])
                explanation = (
                    f"**Impact Analysis:**\n{json_data.get('impact_analysis', 'N/A')}\n\n"
                    f"**Suggested Solution:**\n{json_data.get('solution', 'N/A')}"
                )
                details = {
                    "Issue Found": (
                        f"**Location:** {json_data.get('location_in_prompt', 'N/A')}\n\n"
                        f"**Rationale:** {json_data.get('rationale', 'N/A')}"
                    ),
                }
                category_data = {
                    "items": {"Issue Found": True},
                    "details": details,
                    "explanation": explanation,
                }
            except (json.JSONDecodeError, IndexError):
                category_data = {
                    "items": {"Issue Found": False},
                    "details": {
                        "Issue Found": "Could not parse details for this category.",
                    },
                    "explanation": "There was an error parsing the response from the model.",
                }

        parsed_data[category_name] = category_data

    return parsed_data


def test_parser_logic():
    sample_files = [
        "samples/output.md",
        "samples/output_002.md",
        "samples/output_003.md",
        "samples/output_004.md",
    ]
    for sample_file in sample_files:
        sample_file_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", sample_file),
        )
        if not os.path.exists(sample_file_path):
            print(f"Sample file not found: {sample_file_path}")
            continue
        with open(sample_file_path) as f:
            response = f.read()
        if not response.strip():
            print(f"Sample file is empty: {sample_file}")
            continue

        parsed_dict = parse_evaluation_markdown(response)

        print(f"--- Parsed Dictionary for {sample_file} (first 2 items) ---")
        print(json.dumps({k: parsed_dict[k] for k in list(parsed_dict)[:2]}, indent=2))

        assert isinstance(parsed_dict, dict)
        if "Typos" in parsed_dict:
            assert isinstance(parsed_dict["Typos"]["items"]["Issue Found"], bool)
        if "Punctuation" in parsed_dict:
            assert isinstance(parsed_dict["Punctuation"]["items"]["Issue Found"], bool)
        if "Typos" in parsed_dict:
            assert "details" in parsed_dict["Typos"]
            assert "explanation" in parsed_dict["Typos"]

        print(
            f"\nSuccessfully parsed markdown for {sample_file} and assertions passed!",
        )


if __name__ == "__main__":
    test_parser_logic()
