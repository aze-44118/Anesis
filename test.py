#!/usr/bin/env python3
"""
Standalone test script for audio params pipeline.
Generates a short TTS clip with current audio_params, mixes with theta wave,
and writes the result to database/test_output.wav.
"""

import os
import sys
import numpy as np
import soundfile as sf

# Ensure project root is on the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import AUDIO_CONFIG, PATHS
from main import MeditationPodcastGenerator, load_audio_params


def run_test():
    params = load_audio_params()
    print(f"Audio params: {params}")

    # --- TTS test ---
    print("\n--- TTS generation test ---")
    gen = MeditationPodcastGenerator()
    test_text = "Bienvenue dans cette courte session de test audio."
    audio = gen.generate_tts_audio(test_text, params)
    tts_duration = len(audio) / AUDIO_CONFIG["sample_rate"]
    print(f"TTS result: {len(audio)} samples ({tts_duration:.1f}s)")

    # --- Theta wave mixing test ---
    print("\n--- Theta wave mixing test ---")
    try:
        theta = gen._ensure_theta_resampled()
        mixed = gen.mix_audio_with_background(audio, theta, params.get("theta_volume", 1.0))
        mixed_duration = len(mixed) / AUDIO_CONFIG["sample_rate"]
        print(f"Mixed result: {len(mixed)} samples ({mixed_duration:.1f}s)")
    except Exception as e:
        print(f"Theta mixing skipped: {e}")
        mixed = audio

    # --- Save output ---
    os.makedirs(PATHS["database"], exist_ok=True)
    out_path = os.path.join(PATHS["database"], "test_output.wav")
    sf.write(out_path, mixed, AUDIO_CONFIG["sample_rate"])
    print(f"\n✅ Test output saved: {out_path}")
    print(f"   Duration: {len(mixed)/AUDIO_CONFIG['sample_rate']:.1f}s")


if __name__ == "__main__":
    run_test()
