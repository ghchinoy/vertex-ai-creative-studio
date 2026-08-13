# -*- coding: utf-8 -*-
import json
from unittest.mock import MagicMock, patch
from veo_genetic_prompt_optimizer.evaluate_videos import compare_two_videos, process_video_pair
from veo_genetic_prompt_optimizer.evaluate_prompts import custom_metric_fn


def test_compare_two_videos_flip_logic(tmp_path):
    # Create two dummy video files
    video_a = tmp_path / "vid_a.mp4"
    video_b = tmp_path / "vid_b.mp4"
    video_a.write_bytes(b"dummy video data a")
    video_b.write_bytes(b"dummy video data b")

    client_mock = MagicMock()
    mock_response = MagicMock()
    # If the model judged the first passed video (which was video_b when flipped) as "A"
    mock_response.text = json.dumps({"better_video": "A", "reasoning": "Higher clarity"})
    client_mock.models.generate_content.return_value = mock_response

    # When flipped, model returning "A" should be translated back to "B"
    result = compare_two_videos(
        client=client_mock,
        prompt="A car driving",
        video_a_path=str(video_a),
        video_b_path=str(video_b),
        eval_id="test-eval-1",
        flip_order=True
    )

    assert result["better_video"] == "B"
    assert result["flipped"] is True


def test_process_video_pair_missing_files():
    client_mock = MagicMock()
    result = process_video_pair(
        client=client_mock,
        prompt="A car driving",
        video_a_path="/nonexistent/path/a.mp4",
        video_b_path="/nonexistent/path/b.mp4",
        sampling_count=1,
        flip_enabled=False
    )
    assert result["status"] == "skipped"


def test_custom_metric_fn_score():
    client_mock = MagicMock()
    mock_response = MagicMock()
    mock_response.text = json.dumps({"score": 4.5, "explanation": "High quality cinematic augmentation"})
    client_mock.models.generate_content.return_value = mock_response

    instance = {
        "original_prompt": "a sunset",
        "augmented_prompt": "a breathtaking golden hour sunset over ocean waves"
    }
    schema = {
        "type": "OBJECT",
        "properties": {"score": {"type": "NUMBER"}, "explanation": {"type": "STRING"}},
        "required": ["score", "explanation"]
    }
    res = custom_metric_fn(
        instance=instance,
        client=client_mock,
        metric_template="Original: {original_prompt}, Augmented: {augmented_prompt}",
        metric_name="veo_effectiveness",
        response_schema=schema
    )
    assert res["veo_effectiveness"] == 4.5
    assert "High quality" in res["explanation"]
