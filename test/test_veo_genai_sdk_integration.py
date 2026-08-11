# Copyright 2026 Google LLC
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
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.veo_models import get_models_by_mode
from models.requests import VideoGenerationRequest
from models.veo import generate_video

T2V_MODELS = get_models_by_mode("t2v")
I2V_MODELS = get_models_by_mode("i2v")

REFERENCE_IMAGE = os.environ.get(
    "PERSON_IMAGE",
    "gs://genai-blackbelt-fishfooding-assets/test-cat.png",
)


def _base_request(model_config, **overrides):
    kwargs = dict(
        prompt="a happy dog running on a sunny beach",
        model_version_id=model_config.version_id,
        aspect_ratio=model_config.supported_aspect_ratios[0],
        resolution=model_config.resolutions[0],
        duration_seconds=model_config.default_duration,
        video_count=model_config.default_samples,
        enhance_prompt=model_config.supports_prompt_enhancement,
        generate_audio=False,
        person_generation="Allow (Adults only)",
    )
    kwargs.update(overrides)
    return VideoGenerationRequest(**kwargs)


@pytest.mark.integration
@pytest.mark.parametrize(
    "model_config", T2V_MODELS, ids=[m.version_id for m in T2V_MODELS]
)
def test_t2v_generation_via_genai_sdk(model_config):
    """Text-to-video generation through the genai SDK for each supported model."""
    video_uris, _ = generate_video(_base_request(model_config))
    assert video_uris
    assert all(uri.startswith("gs://") for uri in video_uris)


@pytest.mark.integration
@pytest.mark.parametrize(
    "model_config", I2V_MODELS, ids=[m.version_id for m in I2V_MODELS]
)
def test_i2v_generation_via_genai_sdk(model_config):
    """Image-to-video generation through the genai SDK for each supported model."""
    request = _base_request(model_config, reference_image_gcs=REFERENCE_IMAGE)
    video_uris, _ = generate_video(request)
    assert video_uris
    assert all(uri.startswith("gs://") for uri in video_uris)
