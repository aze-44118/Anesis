#!/usr/bin/env python3
"""
Anesis — AI Meditation Podcast Generator

Generates meditation podcast episodes from structured JSON scripts using
OpenAI TTS and theta-wave background music.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Optional

import numpy as np
import openai
import requests
import soundfile as sf
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from tqdm import tqdm

from config import (
    AUDIO_CONFIG,
    OPENAI_TTS_CONFIG,
    PATHS,
    PODCAST_CONFIG,
    SUPABASE_CONFIG,
    TTS_INSTRUCTION,
    setup_logging,
    validate_config,
)
from supabase_client import SupabasePublisher

logger = logging.getLogger(__name__)

# Audio params file path
_BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
AUDIO_PARAMS_PATH: str = os.path.join(_BASE_DIR, "audio_params.json")


# ---------------------------------------------------------------------------
# Audio parameter helpers
# ---------------------------------------------------------------------------

def load_audio_params() -> dict[str, Any]:
    """Load audio parameters from audio_params.json."""
    with open(AUDIO_PARAMS_PATH, "r") as f:
        return json.load(f)


def save_audio_params(params: dict[str, Any]) -> None:
    """Persist audio parameters to audio_params.json."""
    with open(AUDIO_PARAMS_PATH, "w") as f:
        json.dump(params, f, indent=4)
        f.write("\n")


# ---------------------------------------------------------------------------
# Core generator
# ---------------------------------------------------------------------------

class MeditationPodcastGenerator:
    def __init__(self) -> None:
        from dotenv import load_dotenv

        load_dotenv()

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found. Configure it in your .env file.")

        self.client = openai.OpenAI(api_key=api_key)
        logger.info("OpenAI TTS initialized with voice '%s'", OPENAI_TTS_CONFIG["voice"])

        self.publisher = SupabasePublisher()
        if self.publisher.is_enabled():
            logger.info("Supabase publisher initialized")

    # ------------------------------------------------------------------
    # JSON parsing
    # ------------------------------------------------------------------

    def extract_sentences(
        self, file_path: str, session_name: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Parse a JSON meditation script and return sentences with pause metadata.

        Supports three formats:
        - Flat list of phrase objects
        - Single-key dict wrapping a list
        - Multi-session dict (e.g. ``{"day_1": [...], "day_2": [...]}``
        """
        if not file_path.endswith(".json"):
            raise ValueError("Only JSON files are supported.")

        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        sentences_with_pauses: list[dict[str, Any]] = []
        podcast_key: Optional[str] = None

        def _collect(items: list[Any]) -> None:
            for item in items:
                if isinstance(item, dict) and "text" in item and "pause_after_sec" in item:
                    sentences_with_pauses.append(
                        {
                            "text": item["text"],
                            "pause_after_sec": item["pause_after_sec"],
                            "category": item.get("category", "general"),
                        }
                    )

        if isinstance(data, list):
            _collect(data)
            podcast_key = "podcast"

        elif isinstance(data, dict):
            if len(data) == 0:
                raise ValueError("Invalid JSON: empty object.")

            if len(data) == 1:
                podcast_key = next(iter(data))
                inner = data[podcast_key]
                if not isinstance(inner, list):
                    raise ValueError(
                        f"Invalid JSON: key '{podcast_key}' must contain a list."
                    )
                _collect(inner)

            else:
                available = list(data.keys())
                logger.info(
                    "Multi-session file — %d sessions available: %s",
                    len(available),
                    ", ".join(available),
                )
                if session_name and session_name in available:
                    podcast_key = session_name
                    logger.info("Using specified session: %s", podcast_key)
                else:
                    if session_name:
                        logger.warning(
                            "Session '%s' not found; falling back to first session.", session_name
                        )
                    podcast_key = available[0]
                    logger.info("Using default session: %s", podcast_key)

                inner = data[podcast_key]
                if not isinstance(inner, list):
                    raise ValueError(
                        f"Invalid JSON: session '{podcast_key}' must contain a list."
                    )
                _collect(inner)
        else:
            raise ValueError(
                "Invalid JSON format. Expected a list or an object containing lists."
            )

        if not sentences_with_pauses:
            raise ValueError("No valid phrases found in JSON. Each item needs 'text' and 'pause_after_sec'.")

        logger.info(
            "Extracted %d phrases (key: '%s')", len(sentences_with_pauses), podcast_key
        )
        return {"sentences_with_pauses": sentences_with_pauses, "podcast_key": podcast_key}

    # ------------------------------------------------------------------
    # TTS generation
    # ------------------------------------------------------------------

    @retry(
        retry=retry_if_exception_type(
            (openai.APIConnectionError, openai.RateLimitError, openai.APITimeoutError)
        ),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def _call_openai_tts(self, **kwargs: Any) -> Any:
        """Raw OpenAI TTS call wrapped with retry logic."""
        return self.client.audio.speech.create(**kwargs)

    def generate_tts_audio(
        self, text: str, audio_params: Optional[dict[str, Any]] = None
    ) -> np.ndarray:
        """Generate TTS audio for a single phrase, applying audio_params."""
        return self._generate_openai_tts_audio(text, audio_params)

    def _generate_openai_tts_audio(
        self, text: str, audio_params: Optional[dict[str, Any]] = None
    ) -> np.ndarray:
        """Convert text to a float32 NumPy audio array via OpenAI TTS."""
        try:
            if not text or not text.strip():
                logger.warning("Empty text received — returning 2 s silence.")
                return self.create_silence(2.0)

            speed = 1.0
            if audio_params and audio_params.get("speed", 1.0) != 1.0:
                speed = max(0.25, min(4.0, audio_params["speed"]))

            tts_kwargs: dict[str, Any] = dict(
                model=OPENAI_TTS_CONFIG["model"],
                voice=OPENAI_TTS_CONFIG["voice"],
                input=text,
                response_format=OPENAI_TTS_CONFIG["response_format"],
                instructions=TTS_INSTRUCTION,
                timeout=60,
            )
            if speed != 1.0:
                tts_kwargs["speed"] = speed

            response = self._call_openai_tts(**tts_kwargs)
            logger.debug("TTS response received — %d bytes", len(response.content))

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp.write(response.content)
                tmp_path = tmp.name

            try:
                audio, sr = sf.read(tmp_path, dtype="float32")

                if sr != AUDIO_CONFIG["sample_rate"]:
                    ratio = AUDIO_CONFIG["sample_rate"] / sr
                    new_length = int(len(audio) * ratio)
                    audio = np.interp(
                        np.linspace(0, len(audio), new_length),
                        np.arange(len(audio)),
                        audio,
                    )

                # Pitch shift via resampling
                if audio_params and audio_params.get("tone", 1.0) != 1.0:
                    tone = audio_params["tone"]
                    original_len = len(audio)
                    stretched_len = int(original_len / tone)
                    if stretched_len > 0:
                        audio = np.interp(
                            np.linspace(0, original_len - 1, stretched_len),
                            np.arange(original_len),
                            audio,
                        ).astype(np.float32)

                volume = audio_params.get("volume", 1.0) if audio_params else 1.0
                peak = np.max(np.abs(audio))
                if peak > 0:
                    audio = audio / peak * 0.85 * min(volume, 1.5)

                if len(audio) == 0 or np.max(np.abs(audio)) < 0.001:
                    logger.warning("Generated audio is silent or empty — returning 2 s silence.")
                    return self.create_silence(2.0)

                logger.debug("TTS audio ready: %d samples", len(audio))
                return audio

            except Exception as soundfile_error:
                logger.warning("soundfile read error: %s — returning silence.", soundfile_error)
                return self.create_silence(2.0)
            finally:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

        except RetryError as e:
            logger.error("OpenAI TTS failed after retries: %s", e)
            return self.create_silence(2.0)
        except Exception as e:
            logger.error("OpenAI TTS error: %s", e)
            return self.create_silence(2.0)

    # ------------------------------------------------------------------
    # Audio utilities
    # ------------------------------------------------------------------

    def create_silence(self, duration: float) -> np.ndarray:
        """Return a zero-filled float32 array of the requested duration."""
        try:
            samples = int(duration * AUDIO_CONFIG["sample_rate"])
            return np.zeros(samples, dtype=np.float32)
        except Exception as e:
            logger.warning("Silence creation error: %s", e)
            return np.array([], dtype=np.float32)

    def load_audio_file(self, file_path: str) -> np.ndarray:
        """Load and resample an audio file to the configured sample rate."""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Audio file not found: {file_path}")

            audio, sr = sf.read(file_path, dtype="float32")

            # Safety cap at 40 minutes
            max_samples = 40 * 60 * sr
            if len(audio) > max_samples:
                audio = audio[:max_samples]

            if sr != AUDIO_CONFIG["sample_rate"]:
                ratio = AUDIO_CONFIG["sample_rate"] / sr
                new_length = int(len(audio) * ratio)
                audio = np.interp(
                    np.linspace(0, len(audio), new_length),
                    np.arange(len(audio)),
                    audio,
                )

            return audio

        except Exception as e:
            logger.error("Audio loading error '%s': %s", file_path, e)
            return self.create_silence(1.0)

    def _ensure_theta_resampled(self) -> np.ndarray:
        """Return the theta wave resampled to the configured sample rate, with caching."""
        cache_path = PATHS["theta_wave_cache"]
        if os.path.exists(cache_path):
            audio, sr = sf.read(cache_path, dtype="float32")
            if sr == AUDIO_CONFIG["sample_rate"]:
                logger.info("Theta wave loaded from cache.")
                return audio
            else:
                logger.warning(
                    "Cache sample rate mismatch (%d Hz vs expected %d Hz) — regenerating.",
                    sr,
                    AUDIO_CONFIG["sample_rate"],
                )
                os.unlink(cache_path)

        audio = self.load_audio_file(PATHS["theta_wave"])
        sf.write(cache_path, audio, AUDIO_CONFIG["sample_rate"])
        logger.info("Theta wave resampled to %d Hz and cached.", AUDIO_CONFIG["sample_rate"])
        return audio

    @staticmethod
    def _apply_fade(audio: np.ndarray, fade_samples: int, fade_in: bool = True) -> np.ndarray:
        """Apply a linear fade-in or fade-out over the first/last *fade_samples* samples."""
        if fade_samples <= 0 or len(audio) <= fade_samples:
            return audio
        fade = np.linspace(0.0, 1.0, fade_samples) if fade_in else np.linspace(1.0, 0.0, fade_samples)
        result = audio.copy()
        if fade_in:
            result[:fade_samples] *= fade
        else:
            result[-fade_samples:] *= fade
        return result

    def mix_audio_with_background(
        self,
        foreground: np.ndarray,
        background: np.ndarray,
        theta_volume: float = 1.0,
    ) -> np.ndarray:
        """Mix foreground speech with theta-wave background music."""
        try:
            if len(foreground) == 0 or len(background) == 0:
                logger.warning("Empty audio detected — returning foreground only.")
                return foreground

            sr = AUDIO_CONFIG["sample_rate"]
            target_duration = len(foreground) + int(AUDIO_CONFIG["outro_duration_sec"] * sr)

            # Tile or trim background to target length
            if len(background) < target_duration:
                repeats = int(np.ceil(target_duration / len(background))) + 1
                background = np.tile(background, repeats)
                logger.debug("Background tiled ×%d to cover %.1f s", repeats, target_duration / sr)
            background = background[:target_duration]

            # Fade-in and fade-out (3 seconds each)
            fade_samples = int(3.0 * sr)
            background = self._apply_fade(background, fade_samples, fade_in=True)
            background = self._apply_fade(background, fade_samples, fade_in=False)

            # Extend foreground with silence to match target duration
            if len(foreground) < target_duration:
                foreground = np.concatenate(
                    [foreground, np.zeros(target_duration - len(foreground), dtype=np.float32)]
                )

            mixed = foreground + background * 0.15 * theta_volume

            peak = np.max(np.abs(mixed))
            if peak > 0:
                mixed = mixed / peak * 0.95

            return mixed

        except Exception as e:
            logger.warning("Audio mixing error: %s", e)
            return foreground

    # ------------------------------------------------------------------
    # Main generation pipeline
    # ------------------------------------------------------------------

    def generate_podcast(
        self,
        file_path: str,
        episode_title: str,
        user_id: str,
        session_name: Optional[str] = None,
    ) -> str:
        """
        Generate a complete podcast episode from a JSON script.

        Returns the path to the final output file (MP3 or WAV).
        """
        logger.info("Starting podcast generation: %s", episode_title)

        audio_params = load_audio_params()
        logger.info(
            "Audio params — tone=%.2f  speed=%.2f  volume=%.2f  theta_volume=%.2f",
            audio_params["tone"],
            audio_params["speed"],
            audio_params["volume"],
            audio_params["theta_volume"],
        )

        sentences_data = self.extract_sentences(file_path, session_name)

        if session_name:
            file_name = session_name
        else:
            file_name = re.sub(r"[^\w]", "_", episode_title)
        podcast_title = episode_title

        # Load theta wave
        theta_wave: Optional[np.ndarray] = None
        try:
            theta_wave = self._ensure_theta_resampled()
            logger.info("Theta wave background loaded.")
        except Exception as e:
            logger.warning("Theta wave unavailable: %s — generating without background.", e)

        sentences_to_process = sentences_data["sentences_with_pauses"]
        max_phrases = 150
        if len(sentences_to_process) > max_phrases:
            logger.warning(
                "Phrase count (%d) exceeds limit %d — truncating.",
                len(sentences_to_process),
                max_phrases,
            )
            sentences_to_process = sentences_to_process[:max_phrases]

        # TTS loop
        phrase_audios: list[np.ndarray] = []
        total_tts_seconds = 0.0
        total_pause_seconds = 0.0

        for i, phrase_data in enumerate(
            tqdm(sentences_to_process, desc="Generating TTS", unit="phrase")
        ):
            text: str = phrase_data["text"]
            pause_duration: float = phrase_data["pause_after_sec"]

            audio = self.generate_tts_audio(text, audio_params)

            if len(audio) > 0:
                phrase_audios.append(audio)
                total_tts_seconds += len(audio) / AUDIO_CONFIG["sample_rate"]
            else:
                logger.warning("Empty TTS audio for phrase %d — substituting 2 s silence.", i + 1)
                silence_audio = self.create_silence(2.0)
                phrase_audios.append(silence_audio)
                total_tts_seconds += 2.0

            if i < len(sentences_to_process) - 1:
                phrase_audios.append(self.create_silence(pause_duration))
                total_pause_seconds += pause_duration

        # Assemble
        if phrase_audios:
            try:
                final_audio = np.concatenate(phrase_audios)
            except Exception as e:
                logger.error("Audio assembly error: %s", e)
                final_audio = self.create_silence(5.0)
        else:
            final_audio = np.array([], dtype=np.float32)

        # Prepend 4-second theta intro
        if theta_wave is not None and len(final_audio) > 0:
            try:
                intro = theta_wave[: int(4.0 * AUDIO_CONFIG["sample_rate"])]
                final_audio = np.concatenate([intro, final_audio])
                logger.info("4 s theta-wave intro prepended.")
            except Exception as e:
                logger.warning("Could not prepend theta intro: %s", e)

        total_duration = len(final_audio) / AUDIO_CONFIG["sample_rate"]
        logger.info(
            "Assembly complete — TTS: %.1f s | Pauses: %.1f s | Total: %.1f s",
            total_tts_seconds,
            total_pause_seconds,
            total_duration,
        )

        # Mix with theta background
        if theta_wave is not None:
            logger.info("Mixing with theta-wave background…")
            final_audio = self.mix_audio_with_background(
                final_audio, theta_wave, audio_params.get("theta_volume", 1.0)
            )
            logger.info("Mixing complete.")

        # Save WAV
        output_path: Optional[str] = None
        wav_output_path: Optional[str] = None
        if AUDIO_CONFIG["save_wav"]:
            wav_output_path = os.path.join(PATHS["database"], f"{file_name}.wav")
            try:
                sf.write(wav_output_path, final_audio, AUDIO_CONFIG["sample_rate"])
                logger.info("WAV saved: %s", wav_output_path)
                if not AUDIO_CONFIG["save_mp3"]:
                    output_path = wav_output_path
            except Exception as e:
                logger.error("WAV save error: %s", e)
                if not AUDIO_CONFIG["save_mp3"]:
                    raise

        # Save MP3 via pydub + inject ID3 tags via mutagen
        if AUDIO_CONFIG["save_mp3"]:
            mp3_output_path = os.path.join(PATHS["database"], f"{file_name}.mp3")
            try:
                logger.info("Encoding MP3 at 192 kbps…")
                self._export_mp3(final_audio, mp3_output_path, podcast_title)
                logger.info("MP3 saved: %s", mp3_output_path)
                output_path = mp3_output_path
            except Exception as e:
                logger.error("MP3 encoding error: %s", e)
                if wav_output_path and os.path.exists(wav_output_path):
                    output_path = wav_output_path
                    logger.warning("Falling back to WAV: %s", output_path)
                else:
                    raise RuntimeError("Unable to save podcast (both MP3 and WAV failed).") from e

        if output_path is None:
            raise RuntimeError("No output format configured (both save_wav and save_mp3 are False).")

        # Publish to Supabase
        if self.publisher.is_enabled():
            try:
                logger.info("Publishing to Supabase…")
                mp3_url, rss_url = self.publisher.publish_episode(
                    output_path, file_name, total_duration, podcast_title, user_id
                )
                if mp3_url and rss_url:
                    logger.info("Publication successful. RSS: %s", rss_url)
                else:
                    logger.warning("Supabase publication returned no URLs.")
            except Exception as e:
                logger.error("Supabase publication failed: %s", e)

        return output_path

    def _export_mp3(self, audio: np.ndarray, output_path: str, title: str) -> None:
        """Encode audio as 192 kbps MP3 and inject ID3 tags."""
        from pydub import AudioSegment
        from mutagen.id3 import APIC, COMM, ID3, TALB, TIT2, TPE1

        raw_pcm = (audio * 32767).astype(np.int16).tobytes()
        segment = AudioSegment(
            data=raw_pcm,
            sample_width=2,
            frame_rate=AUDIO_CONFIG["sample_rate"],
            channels=1,
        )
        segment.export(output_path, format="mp3", bitrate="192k")

        # ID3 tags
        tags = ID3(output_path)
        tags.add(TIT2(encoding=3, text=title))
        tags.add(TPE1(encoding=3, text=PODCAST_CONFIG["author"]))
        tags.add(TALB(encoding=3, text=PODCAST_CONFIG["title"]))
        tags.add(COMM(encoding=3, lang="eng", desc="", text=PODCAST_CONFIG["description"]))

        cover_path = os.path.join(_BASE_DIR, "data", PODCAST_CONFIG["cover_filename"])
        if os.path.exists(cover_path):
            with open(cover_path, "rb") as img:
                tags.add(
                    APIC(encoding=3, mime="image/png", type=3, desc="Cover", data=img.read())
                )

        tags.save()


# ---------------------------------------------------------------------------
# CLI command handlers
# ---------------------------------------------------------------------------

def cmd_generate(args: argparse.Namespace) -> None:
    """Generate a podcast from a JSON script."""
    if not os.path.exists(PATHS["theta_wave"]):
        logger.warning("Theta wave not found at '%s' — generation will proceed without it.", PATHS["theta_wave"])

    if not os.path.exists(args.t):
        logger.error("JSON file not found: %s", args.t)
        return

    if not args.t.endswith(".json"):
        logger.error("Only JSON files are supported.")
        return

    generator = MeditationPodcastGenerator()
    try:
        generator.generate_podcast(args.t, args.n, args.id, args.session)
    except Exception as e:
        logger.error("Generation failed: %s", e)


def cmd_set(args: argparse.Namespace) -> None:
    """View or update audio parameters."""
    params = load_audio_params()

    changed = False
    for attr, key in [("tone", "tone"), ("speed", "speed"), ("volume", "volume"), ("theta_volume", "theta_volume")]:
        val = getattr(args, attr, None)
        if val is not None:
            params[key] = val
            changed = True

    if changed:
        save_audio_params(params)
        logger.info("Audio parameters updated.")
    else:
        logger.info("Current audio parameters:")

    for key, val in params.items():
        print(f"  {key}: {val}")


def cmd_upload(args: argparse.Namespace) -> None:
    """Upload an existing MP3 from database/ to Supabase."""
    from dotenv import load_dotenv

    load_dotenv()

    mp3_path = args.file
    if not os.path.isabs(mp3_path):
        mp3_path = os.path.join(PATHS["database"], mp3_path)

    if not os.path.exists(mp3_path):
        logger.error("File not found: %s", mp3_path)
        return

    if not mp3_path.endswith(".mp3"):
        logger.error("Only MP3 files are supported for upload.")
        return

    file_size = os.path.getsize(mp3_path)
    duration_seconds = (file_size * 8) / 128_000
    file_name = os.path.splitext(os.path.basename(mp3_path))[0]
    episode_title = args.n if args.n else file_name

    logger.info("File: %s | Title: %s | Collection: %s | Duration: ~%ds",
                mp3_path, episode_title, args.id, int(duration_seconds))

    publisher = SupabasePublisher()
    if not publisher.is_enabled():
        logger.error("Supabase not configured. Check SUPABASE_URL and SUPABASE_SECRET_KEY in .env")
        return

    try:
        mp3_url, rss_url = publisher.publish_episode(
            mp3_path, file_name, duration_seconds, episode_title, args.id
        )
        if mp3_url and rss_url:
            logger.info("Upload successful. MP3: %s | RSS: %s", mp3_url, rss_url)
        else:
            logger.warning("Upload returned no URLs.")
    except Exception as e:
        logger.error("Upload failed: %s", e)


def cmd_batch(args: argparse.Namespace) -> None:
    """Generate podcasts for all JSON scripts in a directory."""
    script_dir = Path(args.dir)
    if not script_dir.is_dir():
        logger.error("Directory not found: %s", args.dir)
        return

    scripts = sorted(script_dir.glob("*.json"))
    if not scripts:
        logger.warning("No JSON files found in '%s'.", args.dir)
        return

    logger.info("Batch mode: %d script(s) found in '%s'.", len(scripts), args.dir)
    generator = MeditationPodcastGenerator()

    for script_path in scripts:
        episode_name = script_path.stem.replace("_", " ").title()
        logger.info("--- Processing: %s ---", script_path.name)
        try:
            generator.generate_podcast(
                str(script_path), episode_name, args.id, getattr(args, "session", None)
            )
        except Exception as e:
            logger.error("Failed to process '%s': %s", script_path.name, e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    setup_logging()

    try:
        validate_config()
    except EnvironmentError as e:
        logging.critical("%s", e)
        raise SystemExit(1) from e

    parser = argparse.ArgumentParser(
        prog="anesis",
        description="Anesis — AI Meditation Podcast Generator",
    )
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")

    # generate
    gen = subparsers.add_parser("generate", help="Generate a podcast from a JSON script.")
    gen.add_argument("--t", "--text", required=True, dest="t", metavar="PATH",
                     help="Path to JSON script file.")
    gen.add_argument("--n", "--name", required=True, dest="n", metavar="TITLE",
                     help="Episode title (shown in RSS feed).")
    gen.add_argument("--id", required=True, metavar="COLLECTION",
                     help="Collection/folder name in Supabase.")
    gen.add_argument("--session", metavar="SESSION",
                     help="Session key for multi-session JSON files.")

    # set
    st = subparsers.add_parser(
        "set", help="View or update audio parameters (tone, speed, volume, theta_volume)."
    )
    st.add_argument("--tone", type=float, metavar="FLOAT",
                    help="Pitch coefficient (1.0 = default; >1 = higher; <1 = lower).")
    st.add_argument("--speed", type=float, metavar="FLOAT",
                    help="TTS speed (0.25–4.0; default 1.0).")
    st.add_argument("--volume", type=float, metavar="FLOAT",
                    help="Voice volume coefficient (1.0 = default).")
    st.add_argument("--theta_volume", type=float, metavar="FLOAT",
                    help="Theta-wave volume coefficient (1.0 = default).")

    # upload
    upl = subparsers.add_parser("upload", help="Upload an existing MP3 to Supabase.")
    upl.add_argument("--file", required=True, metavar="PATH",
                     help="MP3 filename (relative to database/) or absolute path.")
    upl.add_argument("--n", "--name", dest="n", metavar="TITLE",
                     help="Episode title (defaults to filename).")
    upl.add_argument("--id", required=True, metavar="COLLECTION",
                     help="Collection/folder name in Supabase.")

    # batch
    bat = subparsers.add_parser("batch", help="Process all JSON scripts in a directory.")
    bat.add_argument("--dir", required=True, metavar="DIR",
                     help="Directory containing JSON script files.")
    bat.add_argument("--id", required=True, metavar="COLLECTION",
                     help="Collection/folder name in Supabase.")
    bat.add_argument("--session", metavar="SESSION",
                     help="Session key to use for all multi-session files.")

    args = parser.parse_args()

    dispatch = {
        "generate": cmd_generate,
        "set": cmd_set,
        "upload": cmd_upload,
        "batch": cmd_batch,
    }

    if args.command in dispatch:
        dispatch[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
