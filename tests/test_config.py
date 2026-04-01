"""
Tests for config.py — validate_config and audio parameter helpers.
"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import patch

import pytest

os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")

import main  # noqa: E402 — ensure AUDIO_PARAMS_PATH is importable
from config import validate_config  # noqa: E402


# ---------------------------------------------------------------------------
# validate_config
# ---------------------------------------------------------------------------

class TestValidateConfig:
    def test_raises_when_api_key_missing(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=False):
            with pytest.raises(EnvironmentError, match="OPENAI_API_KEY"):
                validate_config()

    def test_passes_when_api_key_present(self) -> None:
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test-123"}, clear=False):
            validate_config()  # Should not raise


# ---------------------------------------------------------------------------
# Audio parameter roundtrip
# ---------------------------------------------------------------------------

class TestAudioParams:
    def test_save_and_load_roundtrip(self, tmp_path) -> None:
        params_path = str(tmp_path / "audio_params.json")
        original_path = main.AUDIO_PARAMS_PATH
        main.AUDIO_PARAMS_PATH = params_path

        params = {"tone": 0.95, "speed": 0.9, "volume": 0.7, "theta_volume": 1.2}
        main.save_audio_params(params)
        loaded = main.load_audio_params()

        assert loaded == params

        main.AUDIO_PARAMS_PATH = original_path

    def test_saved_file_is_valid_json(self, tmp_path) -> None:
        params_path = str(tmp_path / "audio_params.json")
        original_path = main.AUDIO_PARAMS_PATH
        main.AUDIO_PARAMS_PATH = params_path

        params = {"tone": 1.0, "speed": 1.0, "volume": 1.0, "theta_volume": 1.0}
        main.save_audio_params(params)

        with open(params_path) as f:
            content = f.read()
        parsed = json.loads(content)
        assert parsed == params

        main.AUDIO_PARAMS_PATH = original_path
