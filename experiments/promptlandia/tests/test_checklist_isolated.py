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


# This function is copied directly from pages/checklist.py to avoid dependency issues
def extract_json_from_markdown(response: str):
    """Some prompts return a single JSON object, others return multiple objects that need to be combined"""
    if response.startswith("{"):
        response = "```json\n" + response
    pattern = r"```json\n(.*?)\n```"
    matches = re.findall(pattern, response, re.DOTALL)
    combined = {}
    for match in matches:
        try:
            obj = json.loads(match.strip())
            if isinstance(obj, dict):
                # To handle multiple JSON objects with the same keys,
                # we can merge them. A more sophisticated approach might be needed
                # depending on the desired outcome.
                for key, value in obj.items():
                    if key in combined and isinstance(combined[key], list):
                        if isinstance(value, list):
                            combined[key].extend(value)
                        else:
                            combined[key].append(value)
                    elif key in combined:
                        combined[key] = [combined[key], value]
                    else:
                        combined[key] = value
        except json.JSONDecodeError:
            # Ignore blocks that are not valid JSON
            pass
    return combined


def test_extract_json_from_sample():
    # Construct the absolute path to the sample file
    sample_file_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "samples", "output.md"),
    )

    with open(sample_file_path) as f:
        response = f.read()

    combined_json = extract_json_from_markdown(response)

    # Pretty print the combined JSON to inspect it
    print(json.dumps(combined_json, indent=2))

    # Example of how you might check the data
    assert "issue_name" in combined_json
    assert isinstance(combined_json["issue_name"], list)  # Now a list due to merging
    print("\nSuccessfully extracted and merged JSON from the sample file!")


if __name__ == "__main__":
    test_extract_json_from_sample()
