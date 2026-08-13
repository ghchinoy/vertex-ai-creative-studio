# -*- coding: utf-8 -*-
from unittest.mock import MagicMock
from veo_genetic_prompt_optimizer.prompt_optimizer import (
    select_parents,
    _get_video_paths,
    generate_initial_population,
)


def test_select_parents_ranking_no_tie():
    client_mock = MagicMock()
    candidates = [
        {
            "metaprompt": "prompt A",
            "augmented_prompt_score": 4.0,
            "metaprompt_score": 4.0,
            "intent_preservation_score": 4.0,
        },
        {
            "metaprompt": "prompt B",
            "augmented_prompt_score": 5.0,
            "metaprompt_score": 5.0,
            "intent_preservation_score": 5.0,
        },
        {
            "metaprompt": "prompt C",
            "augmented_prompt_score": 2.0,
            "metaprompt_score": 2.0,
            "intent_preservation_score": 2.0,
        },
    ]

    parents, best_parent = select_parents(client_mock, candidates, top_k=2)

    assert len(parents) == 2
    assert parents[0]["metaprompt"] == "prompt B"
    assert parents[1]["metaprompt"] == "prompt A"
    assert best_parent["metaprompt"] == "prompt B"
    assert parents[0]["combined_score"] == 5.0
    assert parents[1]["combined_score"] == 4.0


def test_get_video_paths():
    prompt_data_text = {"prompt": "A red car driving in a desert"}
    orig, aug, pair_dir = _get_video_paths(prompt_data_text, output_dir="/tmp/test_videos")
    assert "text_a_red_car_driving_in_a_dese" in pair_dir
    assert orig.endswith("original.mp4")
    assert aug.endswith("augmented.mp4")

    prompt_data_img = {"prompt": "Animate this", "image_path": "images/1.png"}
    orig_img, aug_img, pair_dir_img = _get_video_paths(prompt_data_img, output_dir="/tmp/test_videos")
    assert "1" in pair_dir_img
    assert orig_img.endswith("original.mp4")


def test_generate_initial_population_fallback():
    client_mock = MagicMock()
    # Simulate API returning empty or failing
    client_mock.models.generate_content.side_effect = Exception("API error")

    pop = generate_initial_population(client_mock, "Base metaprompt", size=4)
    assert len(pop) == 4
    assert pop[0]["metaprompt"] == "Base metaprompt"
    assert pop[0]["provenance"]["type"] == "initial_base"
    for item in pop[1:]:
        assert item["provenance"]["type"] == "initial_variation"
