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

import os
import sys
from unittest.mock import MagicMock

import pytest

# Ensure dummy env vars exist for tests when running without GCP environment
os.environ.setdefault("PROJECT_ID", "test-project")
os.environ.setdefault("LOCATION", "us-central1")
os.environ.setdefault("VEO_PROJECT_ID", "test-project")
os.environ.setdefault("VEO_LOCATION", "us-central1")

# Mock parselmouth if not installed in testing environment
if "parselmouth" not in sys.modules:
    try:
        import parselmouth  # noqa: F401
    except ImportError:
        mock_pm = MagicMock()
        sys.modules["parselmouth"] = mock_pm
        sys.modules["parselmouth.praat"] = mock_pm.praat


def pytest_addoption(parser):
    """Adds a custom command-line option to pytest for specifying the GCS bucket."""
    parser.addoption(
        "--gcs-bucket",
        action="store",
        default="gs://genai-blackbelt-fishfooding-assets",
        help="The GCS bucket to use for tests that require GCS resources.",
    )


@pytest.fixture
def gcs_bucket_for_tests(request):
    """A pytest fixture that provides the GCS bucket from the command-line option."""
    return request.config.getoption("--gcs-bucket")
