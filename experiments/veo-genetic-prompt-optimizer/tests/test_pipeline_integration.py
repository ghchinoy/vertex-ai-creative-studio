# -*- coding: utf-8 -*-
import json
import os
from unittest.mock import MagicMock, patch
from pathlib import Path

from veo_genetic_prompt_optimizer import prompt_optimizer, generate_prompts, run_pipeline


def test_full_pipeline_run_mocked(tmp_path, monkeypatch):
    # Setup isolated test directory
    prompts_file = tmp_path / "test_prompts.json"
    prompts_file.write_text(json.dumps([{"prompt": "A drone shot of a misty mountain peak."}]))
    
    out_metaprompt = tmp_path / "optimized_metaprompt.py"
    out_history = tmp_path / "optimization_history.json"
    out_augmented = tmp_path / "augmented_prompts.json"

    # Mock Gemini generation
    def mock_generate_content(model, contents, config=None):
        resp = MagicMock()
        # Initial population variation response
        if getattr(config, 'response_schema', None) and config.response_schema.get('type') == 'ARRAY':
            resp.text = json.dumps([
                "Augment this prompt with cinematic drone camera movements and dramatic morning lighting."
            ])
            return resp
        
        # Tie break judge or single score response
        if getattr(config, 'response_schema', None) and config.response_schema.get('type') == 'OBJECT':
            resp.text = json.dumps({
                "score": 4.5,
                "reasoning": "Strong cinematic enhancement",
                "explanation": "Preserves core mountain subject well"
            })
            return resp

        # General text generation (mutation / crossover / prompt rewrite)
        resp.text = "Cinematic aerial drone shot slowly ascending over a misty mountain peak during sunrise."
        return resp

    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = mock_generate_content

    # Mock evaluate_pointwise_batch
    import pandas as pd
    def mock_evaluate_pointwise_batch(prompts_data, metric_name, metric_template, experiment, sampling_count=1):
        summary = {f"{metric_name}/mean": 4.5}
        matrix = pd.DataFrame([{f"{metric_name}/explanation": "Excellent adherence to visual cinematic style."}])
        return summary, matrix

    monkeypatch.setattr(prompt_optimizer, "get_genai_client", lambda: mock_client)
    monkeypatch.setattr(generate_prompts, "get_genai_client", lambda: mock_client)
    monkeypatch.setattr("veo_genetic_prompt_optimizer.evaluate_prompts.evaluate_pointwise_batch", mock_evaluate_pointwise_batch)
    monkeypatch.setattr("veo_genetic_prompt_optimizer.prompt_optimizer.evaluate_prompts.evaluate_pointwise_batch", mock_evaluate_pointwise_batch)

    # 1. Run prompt optimizer with 2 generations, population size 2
    monkeypatch.setattr("sys.argv", [
        "prompt_optimizer.py",
        "--generations", "2",
        "--population-size", "2",
        "--top-k", "1",
        "--prompts", str(prompts_file),
        "--output-metaprompt", str(out_metaprompt),
        "--history", str(out_history)
    ])
    prompt_optimizer.main()

    assert out_metaprompt.exists()
    assert out_history.exists()
    
    with open(out_history, "r") as f:
        history_data = json.load(f)
    assert len(history_data) == 2
    assert "best_parent" in history_data[-1]

    # 2. Run generate_prompts
    monkeypatch.setattr("sys.argv", [
        "generate_prompts.py",
        "--history", str(out_history),
        "--prompts", str(prompts_file),
        "--output", str(out_augmented)
    ])
    generate_prompts.main()

    assert out_augmented.exists()
    with open(out_augmented, "r") as f:
        augmented_data = json.load(f)
    assert len(augmented_data) == 1
    assert "augmented_prompt" in augmented_data[0]
    assert augmented_data[0]["original_prompt"] == "A drone shot of a misty mountain peak."


def test_run_pipeline_cli_skip_flags(monkeypatch):
    step_calls = []

    monkeypatch.setattr("veo_genetic_prompt_optimizer.prompt_optimizer.main", lambda: step_calls.append("optimizer"))
    monkeypatch.setattr("veo_genetic_prompt_optimizer.generate_prompts.main", lambda: step_calls.append("prompts"))
    monkeypatch.setattr("veo_genetic_prompt_optimizer.generate_videos.main", lambda: step_calls.append("videos"))
    monkeypatch.setattr("veo_genetic_prompt_optimizer.evaluate_videos.main", lambda: step_calls.append("eval_videos"))

    monkeypatch.setattr("sys.argv", ["run_pipeline.py", "--skip-videos", "--skip-optimizer"])
    run_pipeline.main()

    assert "optimizer" not in step_calls
    assert "prompts" in step_calls
    assert "videos" not in step_calls
    assert "eval_videos" not in step_calls
