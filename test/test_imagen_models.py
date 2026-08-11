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

"""Unit tests for the Imagen model source-of-truth list (``config.imagen_models``).

These are pure-config tests (no network, no mesop) that guard the GA endpoint
deprecation: the sunsetting Imagen 3 generate endpoints must stay out of
``IMAGEN_MODELS``, the go-forward Imagen 4 tiers must remain, and lookups keyed
on a removed model id must fail soft (return ``None``) rather than raise.
"""

# Setup sys.path to allow imports from the parent directory.
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest

from config.imagen_models import (
    IMAGEN_MODELS,
    ImagenModelConfig,
    get_imagen_model_config,
)

# Imagen 3 generate endpoints removed under the GA sunset (2026-06-30).
REMOVED_IMAGEN_MODEL_IDS = [
    "imagen-3.0-fast-generate-001",
    "imagen-3.0-generate-002",
]

# Go-forward tiers that must remain selectable.
EXPECTED_IMAGEN_MODEL_IDS = [
    "imagen-4.0-generate-001",       # page default (state/imagen_state.py)
    "imagen-4.0-fast-generate-001",  # fast-tier replacement for imagen-3.0-fast
    "imagen-4.0-ultra-generate-001",
]


def _model_names():
    return {m.model_name for m in IMAGEN_MODELS}


@pytest.mark.parametrize("removed_id", REMOVED_IMAGEN_MODEL_IDS)
def test_sunsetting_imagen_models_removed_from_list(removed_id):
    """The deprecated Imagen 3 generate endpoints are gone from the dropdown source."""
    assert removed_id not in _model_names(), (
        f"{removed_id} sunsets on 2026-06-30 and must not be selectable in IMAGEN_MODELS"
    )


@pytest.mark.parametrize("expected_id", EXPECTED_IMAGEN_MODEL_IDS)
def test_expected_imagen_models_present(expected_id):
    """The Imagen 4 go-forward tiers remain in the source-of-truth list."""
    assert expected_id in _model_names(), (
        f"{expected_id} is a required go-forward Imagen model and must stay in IMAGEN_MODELS"
    )


def test_imagen_models_are_well_formed():
    """Every remaining entry is a fully-populated ImagenModelConfig."""
    assert IMAGEN_MODELS, "IMAGEN_MODELS must not be empty"
    for model in IMAGEN_MODELS:
        assert isinstance(model, ImagenModelConfig)
        assert model.model_name
        assert model.display_name
        assert model.supported_aspect_ratios
        assert model.default_samples >= 1
        assert model.max_samples >= model.default_samples


@pytest.mark.parametrize("removed_id", REMOVED_IMAGEN_MODEL_IDS)
def test_lookup_of_removed_model_fails_soft(removed_id):
    """Persisted state / library metadata pointing at a removed model must fail soft.

    A user whose saved state references a now-removed Imagen id must not crash the
    page: ``get_imagen_model_config`` returns ``None`` (callers fall back to the
    default / render a "no model configuration" message) instead of raising.
    """
    result = get_imagen_model_config(removed_id)
    assert result is None


def test_lookup_of_unknown_model_fails_soft():
    """An arbitrary unknown model id also resolves to None, never an exception."""
    assert get_imagen_model_config("some-model-that-never-existed") is None


def test_lookup_of_valid_model_resolves():
    """A surviving model id still resolves to its config (sanity check)."""
    config = get_imagen_model_config("imagen-4.0-generate-001")
    assert config is not None
    assert config.model_name == "imagen-4.0-generate-001"
