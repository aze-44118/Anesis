"""
Tests for MeditationPodcastGenerator core audio logic.
All OpenAI API calls are mocked — no network access required.
"""
from __future__ import annotations

import json
import os
import tempfile
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# Provide a fake API key so config.validate_config() does not raise during import
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")


from main import MeditationPodcastGenerator, load_audio_params, save_audio_params  # noqa: E402
from config import AUDIO_CONFIG  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def generator() -> MeditationPodcastGenerator:
    """Return a generator with a mocked OpenAI client."""
    with patch("main.openai.OpenAI"):
        gen = MeditationPodcastGenerator()
    return gen


@pytest.fixture()
def flat_script(tmp_path) -> str:
    """Write a flat-list JSON script and return its path."""
    data = [
        {"text": "Welcome.", "pause_after_sec": 5, "category": "induction"},
        {"text": "Breathe.", "pause_after_sec": 10, "category": "breathing"},
    ]
    p = tmp_path / "flat.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


@pytest.fixture()
def nested_script(tmp_path) -> str:
    """Write a single-key nested JSON script and return its path."""
    data = {
        "morning": [
            {"text": "Good morning.", "pause_after_sec": 3, "category": "induction"},
        ]
    }
    p = tmp_path / "nested.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


@pytest.fixture()
def multisession_script(tmp_path) -> str:
    """Write a multi-session JSON script and return its path."""
    data = {
        "day_1": [{"text": "Day one.", "pause_after_sec": 4, "category": "induction"}],
        "day_2": [{"text": "Day two.", "pause_after_sec": 4, "category": "induction"}],
    }
    p = tmp_path / "multi.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return str(p)


# ---------------------------------------------------------------------------
# Silence tests
# ---------------------------------------------------------------------------

class TestCreateSilence:
    def test_correct_duration(self, generator: MeditationPodcastGenerator) -> None:
        audio = generator.create_silence(2.0)
        expected = int(2.0 * AUDIO_CONFIG["sample_rate"])
        assert len(audio) == expected

    def test_zero_duration(self, generator: MeditationPodcastGenerator) -> None:
        audio = generator.create_silence(0.0)
        assert len(audio) == 0

    def test_dtype_is_float32(self, generator: MeditationPodcastGenerator) -> None:
        audio = generator.create_silence(1.0)
        assert audio.dtype == np.float32

    def test_all_zeros(self, generator: MeditationPodcastGenerator) -> None:
        audio = generator.create_silence(1.0)
        assert np.all(audio == 0.0)


# ---------------------------------------------------------------------------
# JSON parsing tests
# ---------------------------------------------------------------------------

class TestExtractSentences:
    def test_flat_list_format(self, generator: MeditationPodcastGenerator, flat_script: str) -> None:
        result = generator.extract_sentences(flat_script)
        assert len(result["sentences_with_pauses"]) == 2
        assert result["sentences_with_pauses"][0]["text"] == "Welcome."
        assert result["podcast_key"] == "podcast"

    def test_nested_format(self, generator: MeditationPodcastGenerator, nested_script: str) -> None:
        result = generator.extract_sentences(nested_script)
        assert len(result["sentences_with_pauses"]) == 1
        assert result["podcast_key"] == "morning"

    def test_multisession_explicit_key(
        self, generator: MeditationPodcastGenerator, multisession_script: str
    ) -> None:
        result = generator.extract_sentences(multisession_script, session_name="day_2")
        assert result["sentences_with_pauses"][0]["text"] == "Day two."
        assert result["podcast_key"] == "day_2"

    def test_multisession_defaults_to_first(
        self, generator: MeditationPodcastGenerator, multisession_script: str
    ) -> None:
        result = generator.extract_sentences(multisession_script)
        assert result["podcast_key"] == "day_1"

    def test_empty_list_raises(self, generator: MeditationPodcastGenerator, tmp_path) -> None:
        p = tmp_path / "empty.json"
        p.write_text("[]", encoding="utf-8")
        with pytest.raises(ValueError, match="No valid phrases"):
            generator.extract_sentences(str(p))

    def test_non_json_raises(self, generator: MeditationPodcastGenerator) -> None:
        with pytest.raises(ValueError, match="Only JSON"):
            generator.extract_sentences("script.txt")


# ---------------------------------------------------------------------------
# TTS audio tests (mocked)
# ---------------------------------------------------------------------------

class TestGenerateTTSAudio:
    def _make_wav_bytes(self) -> bytes:
        """Create minimal valid WAV bytes (44-byte header + 1000 samples of silence)."""
        import struct
        import wave
        import io

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(AUDIO_CONFIG["sample_rate"])
            w.writeframes(b"\x10\x00" * 2000)  # non-silent PCM data
        return buf.getvalue()

    def test_returns_ndarray(self, generator: MeditationPodcastGenerator) -> None:
        mock_response = MagicMock()
        mock_response.content = self._make_wav_bytes()
        generator._call_openai_tts = MagicMock(return_value=mock_response)

        result = generator.generate_tts_audio("Hello world")
        assert isinstance(result, np.ndarray)
        assert len(result) > 0

    def test_empty_text_returns_silence(self, generator: MeditationPodcastGenerator) -> None:
        result = generator.generate_tts_audio("")
        silence_len = int(2.0 * AUDIO_CONFIG["sample_rate"])
        assert len(result) == silence_len

    def test_whitespace_text_returns_silence(self, generator: MeditationPodcastGenerator) -> None:
        result = generator.generate_tts_audio("   ")
        silence_len = int(2.0 * AUDIO_CONFIG["sample_rate"])
        assert len(result) == silence_len


# ---------------------------------------------------------------------------
# Audio mixing tests
# ---------------------------------------------------------------------------

class TestMixAudioWithBackground:
    def _make_audio(self, seconds: float) -> np.ndarray:
        samples = int(seconds * AUDIO_CONFIG["sample_rate"])
        return np.ones(samples, dtype=np.float32) * 0.5

    def test_output_length_equals_foreground_plus_outro(
        self, generator: MeditationPodcastGenerator
    ) -> None:
        fg = self._make_audio(10.0)
        bg = self._make_audio(60.0)
        mixed = generator.mix_audio_with_background(fg, bg)
        expected = len(fg) + int(AUDIO_CONFIG["outro_duration_sec"] * AUDIO_CONFIG["sample_rate"])
        assert len(mixed) == expected

    def test_empty_foreground_returns_foreground(
        self, generator: MeditationPodcastGenerator
    ) -> None:
        fg = np.array([], dtype=np.float32)
        bg = self._make_audio(5.0)
        result = generator.mix_audio_with_background(fg, bg)
        assert len(result) == 0

    def test_peak_normalized(self, generator: MeditationPodcastGenerator) -> None:
        fg = self._make_audio(5.0)
        bg = self._make_audio(60.0)
        mixed = generator.mix_audio_with_background(fg, bg)
        assert np.max(np.abs(mixed)) <= 0.96  # normalized to 0.95 ± float tolerance

    def test_fade_reduces_start_and_end(self, generator: MeditationPodcastGenerator) -> None:
        fg = self._make_audio(5.0)
        bg = self._make_audio(60.0)
        mixed = generator.mix_audio_with_background(fg, bg, theta_volume=10.0)
        sr = AUDIO_CONFIG["sample_rate"]
        # First sample should be near-zero (fade-in) after normalization
        assert abs(mixed[0]) < abs(mixed[sr * 4])


# ---------------------------------------------------------------------------
# Theta cache tests
# ---------------------------------------------------------------------------

class TestEnsureThetaResampled:
    def test_stale_cache_deleted_and_regenerated(
        self, generator: MeditationPodcastGenerator, tmp_path
    ) -> None:
        import soundfile as sf

        # Write a cache file at a wrong sample rate
        stale_audio = np.zeros(1000, dtype=np.float32)
        stale_path = str(tmp_path / "theta_cache.wav")
        sf.write(stale_path, stale_audio, 22050)  # wrong sample rate

        correct_audio = np.ones(4000, dtype=np.float32) * 0.1
        correct_path = str(tmp_path / "theta_source.wav")
        sf.write(correct_path, correct_audio, AUDIO_CONFIG["sample_rate"])

        from config import PATHS as _PATHS

        original_cache = _PATHS["theta_wave_cache"]
        original_source = _PATHS["theta_wave"]
        _PATHS["theta_wave_cache"] = stale_path
        _PATHS["theta_wave"] = correct_path

        try:
            result = generator._ensure_theta_resampled()
            # Stale file should have been replaced
            loaded, sr = sf.read(stale_path)
            assert sr == AUDIO_CONFIG["sample_rate"]
        finally:
            _PATHS["theta_wave_cache"] = original_cache
            _PATHS["theta_wave"] = original_source


# ---------------------------------------------------------------------------
# Static helpers
# ---------------------------------------------------------------------------

class TestApplyFade:
    def test_fade_in_starts_near_zero(self) -> None:
        audio = np.ones(44100, dtype=np.float32)
        faded = MeditationPodcastGenerator._apply_fade(audio, 1000, fade_in=True)
        assert faded[0] == pytest.approx(0.0, abs=0.01)
        assert faded[-1] == pytest.approx(1.0, abs=0.01)

    def test_fade_out_ends_near_zero(self) -> None:
        audio = np.ones(44100, dtype=np.float32)
        faded = MeditationPodcastGenerator._apply_fade(audio, 1000, fade_in=False)
        assert faded[-1] == pytest.approx(0.0, abs=0.01)
        assert faded[0] == pytest.approx(1.0, abs=0.01)

    def test_no_op_when_fade_samples_zero(self) -> None:
        audio = np.ones(100, dtype=np.float32)
        result = MeditationPodcastGenerator._apply_fade(audio, 0)
        np.testing.assert_array_equal(result, audio)
