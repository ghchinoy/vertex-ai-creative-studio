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

# Parametrize over each text-to-video capable model in the configuration.
T2V_MODELS = get_models_by_mode("t2v")


@pytest.mark.integration
@pytest.mark.parametrize(
    "model_config", T2V_MODELS, ids=[m.version_id for m in T2V_MODELS]
)
def test_veo_t2v_api_call(model_config):
    """An integration test that calls the real VEO API for text-to-video.

    This test is marked as 'integration' and will be skipped unless explicitly
    run with 'pytest -m integration'. It verifies that the application can
    successfully communicate with the live VEO API and receive a valid response
    for every supported model.
    """
    # --- Arrange ---
    # Use a simple, reliable prompt that is unlikely to trigger content filters.
    request = VideoGenerationRequest(
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

    # --- Act ---
    # Call the actual generation function, which makes a real API call and
    # returns (video_uris, resolution).
    video_uris, resolution = generate_video(request)

    # --- Assert ---
    print(f"\n--- API response for model {model_config.version_id} ---")
    print(video_uris)
    print("----------------------------------------------------")

    assert video_uris, "The API should return at least one generated video URI."
    for uri in video_uris:
        assert uri.startswith("gs://"), f"Expected a GCS URI, got {uri}"
    assert resolution == request.resolution

    print(
        f"\nIntegration test for model {model_config.version_id} PASSED. "
        f"Videos generated: {video_uris}"
    )
