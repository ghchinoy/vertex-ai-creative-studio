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

"""Component test for the Veo generation flow's metadata handling.

The synchronous on_click_veo path this file previously targeted was refactored
into an async job flow; the MediaItem metadata (including the resolved model
name) is now built in services.veo_service.create_initial_job. This test
exercises that function directly, verifying both the happy path for a
still-supported model and the fail-soft path for a GA-sunset model id.
"""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from common.metadata import MediaItem
from config.veo_models import VEO_MODELS
from models.requests import VideoGenerationRequest
from services.veo_service import create_initial_job

# A still-supported model to drive the happy-path assertions.
SUPPORTED_MODEL = VEO_MODELS[0]


def _request(model_version_id):
    return VideoGenerationRequest(
        prompt="a test prompt for veo",
        model_version_id=model_version_id,
        aspect_ratio="16:9",
        resolution="720p",
        duration_seconds=5,
        video_count=1,
        enhance_prompt=False,
        generate_audio=False,
        person_generation="Allow (Adults only)",
    )


@patch("services.veo_service.add_media_item_to_firestore")
def test_create_initial_job_logs_correct_model_metadata(mock_add_media_item):
    """A job for a supported model logs a MediaItem with the resolved model_name."""
    request = _request(SUPPORTED_MODEL.version_id)

    create_initial_job(request, user_email="test_user@example.com")

    mock_add_media_item.assert_called_once()
    media_item_logged = mock_add_media_item.call_args[0][0]

    assert isinstance(media_item_logged, MediaItem)
    assert media_item_logged.user_email == "test_user@example.com"
    assert media_item_logged.prompt == "a test prompt for veo"
    assert media_item_logged.mode == "t2v"
    # The model name is resolved from config for a supported version_id.
    assert media_item_logged.model == SUPPORTED_MODEL.model_name


@patch("services.veo_service.add_media_item_to_firestore")
def test_create_initial_job_fails_soft_for_removed_model(mock_add_media_item):
    """A job referencing a GA-sunset model id must NOT raise; it falls back to
    recording the raw model_version_id rather than crashing on a None config."""
    removed_id = "veo-2.0-generate-001"
    request = _request(removed_id)

    # Should not raise despite the model no longer existing in VEO_MODELS.
    create_initial_job(request, user_email="test_user@example.com")

    mock_add_media_item.assert_called_once()
    media_item_logged = mock_add_media_item.call_args[0][0]
    assert media_item_logged.model == removed_id
