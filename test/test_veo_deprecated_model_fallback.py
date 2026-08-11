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

"""Regression tests: references to GA-sunset Veo models must fail soft.

After the GA sunset, veo-2.0-generate-001, veo-3.0-generate-001, and
veo-3.0-fast-generate-001 were removed from VEO_MODELS. Persisted state and
library metadata created before the sunset can still reference those ids, so the
config lookups and the display/version resolution the app performs on them must
degrade gracefully (return None / fall back to a default) rather than raise.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config.veo_models import (
    DEFAULT_VEO_VERSION_ID,
    VEO_MODELS,
    get_veo_model_config,
    get_version_id_by_model_name,
)

# version_id / model_name pairs that were removed at the GA sunset.
REMOVED_VERSION_IDS = ["2.0", "3.0", "3.0-fast"]
REMOVED_MODEL_NAMES = [
    "veo-2.0-generate-001",
    "veo-3.0-generate-001",
    "veo-3.0-fast-generate-001",
]


@pytest.mark.parametrize("version_id", REMOVED_VERSION_IDS)
def test_get_veo_model_config_returns_none_for_removed(version_id):
    """Looking up a removed version_id returns None instead of raising."""
    assert get_veo_model_config(version_id) is None


@pytest.mark.parametrize("model_name", REMOVED_MODEL_NAMES)
def test_get_version_id_by_model_name_returns_none_for_removed(model_name):
    """Looking up a removed model_name returns None instead of raising."""
    assert get_version_id_by_model_name(model_name) is None


@pytest.mark.parametrize("model_name", REMOVED_MODEL_NAMES)
def test_version_resolution_falls_back_to_default(model_name):
    """The `or default` resolution pattern used across the app (e.g. object
    rotation / interior design / DEFAULT_VEO_VERSION_ID) yields a valid,
    still-supported model when metadata references a removed id."""
    valid_version_ids = {m.version_id for m in VEO_MODELS}

    # This mirrors the fail-soft pattern used at call sites throughout the app.
    resolved = get_version_id_by_model_name(model_name) or DEFAULT_VEO_VERSION_ID

    assert resolved in valid_version_ids
    # And the resolved id is itself resolvable to a live config.
    assert get_veo_model_config(resolved) is not None


@pytest.mark.parametrize("model_name", REMOVED_MODEL_NAMES)
def test_display_resolution_does_not_raise_for_removed(model_name):
    """Display/version resolution of a persisted removed model id degrades to a
    'model unavailable' style fallback rather than raising AttributeError."""
    version_id = get_version_id_by_model_name(model_name)
    config = get_veo_model_config(version_id) if version_id else None

    # Guarded attribute access (the pattern used in the UI/service layers).
    display_name = config.display_name if config else "Model unavailable"

    assert display_name == "Model unavailable"


def test_default_veo_version_id_is_supported():
    """The module-level default must always resolve to a live config."""
    assert get_veo_model_config(DEFAULT_VEO_VERSION_ID) is not None
