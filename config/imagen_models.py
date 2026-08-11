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

from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ImagenModelConfig:
    """Configuration for a specific Imagen model version."""
    model_name: str
    display_name: str
    supported_aspect_ratios: List[str]
    max_samples: int
    default_samples: int

# This list is the single source of truth for all Imagen model configurations.
#
# GA endpoint deprecation (sunset 2026-06-30): the Imagen 3 generate endpoints
# `imagen-3.0-fast-generate-001` and `imagen-3.0-generate-002` were removed from
# this list. Their go-forward replacements are already present below:
# `imagen-4.0-fast-generate-001` (fast tier) and `imagen-4.0-generate-001`
# (standard tier, also the page default). Do not re-add the Imagen 3 entries.
IMAGEN_MODELS: List[ImagenModelConfig] = [
    ImagenModelConfig(
        model_name="imagen-4.0-generate-001",
        display_name="Imagen 4",
        supported_aspect_ratios=["1:1", "3:4", "4:3", "9:16", "16:9"],
        max_samples=4,
        default_samples=4,
    ),
    ImagenModelConfig(
        model_name="imagen-4.0-fast-generate-001",
        display_name="Imagen 4 Fast",
        supported_aspect_ratios=["1:1", "3:4", "4:3", "9:16", "16:9"],
        max_samples=4,
        default_samples=4,
    ),
    ImagenModelConfig(
        model_name="imagen-4.0-ultra-generate-001",
        display_name="Imagen 4 Ultra",
        supported_aspect_ratios=["1:1", "3:4", "4:3", "9:16", "16:9"],
        max_samples=1,
        default_samples=1,
    ),
]

# Helper function to easily find a model's config by its model_name.
def get_imagen_model_config(model_name: str) -> Optional[ImagenModelConfig]:
    """Finds and returns the configuration for a given Imagen model name."""
    for model in IMAGEN_MODELS:
        if model.model_name == model_name:
            return model
    return None
