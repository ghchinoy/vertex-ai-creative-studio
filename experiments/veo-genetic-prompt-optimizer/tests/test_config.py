# -*- coding: utf-8 -*-
import os
from pathlib import Path
from veo_genetic_prompt_optimizer import config


def test_config_defaults():
    assert config.GEMINI_MODEL_ID == os.getenv("GEMINI_MODEL_ID", "gemini-3.6-flash")
    assert config.LOCATION in ("global", os.getenv("LOCATION", "global"))
    assert config.POPULATION_SIZE >= 2
    assert config.NUM_GENERATIONS >= 1
    assert config.AUGMENTED_PROMPT_SCORE_WEIGHT + config.METAPROMPT_SCORE_WEIGHT + config.INTENT_PRESERVATION_SCORE_WEIGHT == 1.0


def test_resolve_path():
    guide_path = config.resolve_path("veo_guide.md")
    assert guide_path.exists()
    assert guide_path.name == "veo_guide.md"
