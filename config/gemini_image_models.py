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

from dataclasses import dataclass, field


@dataclass
class GeminiImageModelConfig:
    """Configuration for a specific Gemini Image Generation model version."""

    version_id: str  # Short ID for UI/Logic (e.g., "2.5-flash", "3.0-pro")
    model_name: str  # Full API Model ID (e.g., "gemini-2.5-flash-image")
    display_name: str  # Human-readable name (e.g., "Gemini 2.5 Flash")

    # Capabilities
    max_input_images: int
    max_output_images: int
    requires_base_url: bool = False

    supported_aspect_ratios: list[str] = field(
        default_factory=lambda: [
            "1:1",
            "3:2",
            "2:3",
            "3:4",
            "4:3",
            "4:5",
            "5:4",
            "9:16",
            "16:9",
            "21:9",
        ],
    )
    supported_image_sizes: list[str] = field(
        default_factory=lambda: ["1K", "2K"],
    )

    # Future-proofing
    supports_negative_prompt: bool = False
    supports_person_generation_filter: bool = True
    supports_search: bool = False


# Single source of truth
GEMINI_IMAGE_MODELS: list[GeminiImageModelConfig] = [
    GeminiImageModelConfig(
        version_id="2.5-flash",
        model_name="gemini-2.5-flash-image",
        display_name="Gemini 2.5 Flash",
        max_input_images=3,
        max_output_images=1,
        requires_base_url=False,
        supported_image_sizes=["1K", "2K"],
        supports_search=False,
    ),
    GeminiImageModelConfig(
        version_id="3.0-pro-preview",
        model_name="gemini-3-pro-image-preview",
        display_name="Gemini 3.0 Pro Preview",
        max_input_images=6,
        max_output_images=10,
        requires_base_url=True,
        supported_image_sizes=["1K", "2K", "4K"],
        supports_search=True,
    ),
]


def get_gemini_image_model_config(
    model_name_or_version: str,
) -> GeminiImageModelConfig | None:
    """Finds config by either full model name or short version ID."""
    for model in GEMINI_IMAGE_MODELS:
        if (
            model.model_name == model_name_or_version
            or model.version_id == model_name_or_version
        ):
            return model
    return None
