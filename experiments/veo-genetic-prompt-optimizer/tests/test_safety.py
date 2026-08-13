# -*- coding: utf-8 -*-
from unittest.mock import MagicMock
from veo_genetic_prompt_optimizer.rewrite_prompt_for_safety import sanitize_prompt


def test_sanitize_prompt():
    client_mock = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "A cinematic shot of people walking in a park."
    client_mock.models.generate_content.return_value = mock_response

    sanitized = sanitize_prompt(client_mock, "A shot of children in a park.")
    assert sanitized == "A cinematic shot of people walking in a park."
    client_mock.models.generate_content.assert_called_once()
