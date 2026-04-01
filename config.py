"""
Anesis — AI Meditation Podcast Generator
Configuration module: constants, validation, and logging setup.
"""
from __future__ import annotations

import logging
import os
from importlib.metadata import PackageNotFoundError, version

# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------
try:
    __version__: str = version("anesis")
except PackageNotFoundError:
    __version__ = "2.0.0-dev"

# ---------------------------------------------------------------------------
# OpenAI TTS
# ---------------------------------------------------------------------------
OPENAI_TTS_CONFIG: dict = {
    "voice": "onyx",
    "model": "gpt-4o-mini-tts",
    "response_format": "wav",
}

# Meditation guide voice instruction (French)
TTS_INSTRUCTION: str = (
    "Voix grave et posée de guide de méditation. Parle lentement, avec une "
    "profondeur sombre et apaisante. Chaque mot est déposé avec intention, "
    "comme un murmure solennel. Longues pauses naturelles entre les groupes "
    "de mots. Ton descendant en fin de phrase, jamais montant. Rythme "
    "hypnotique et régulier, presque monotone. Aucune énergie, aucune "
    "urgence. Présence grave, enveloppante et contemplative."
)

# ---------------------------------------------------------------------------
# Audio processing
# ---------------------------------------------------------------------------
AUDIO_CONFIG: dict = {
    "sample_rate": 44100,
    "outro_duration_sec": 30,
    "save_wav": True,
    "save_mp3": True,
}

# ---------------------------------------------------------------------------
# File paths (absolute, anchored to project root)
# ---------------------------------------------------------------------------
_BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))

PATHS: dict = {
    "theta_wave": os.path.join(_BASE_DIR, "data", "theta_wave.wav"),
    "theta_wave_cache": os.path.join(_BASE_DIR, "data", "theta_wave_44100.wav"),
    "database": os.path.join(_BASE_DIR, "database"),
}

# ---------------------------------------------------------------------------
# Podcast / RSS / Supabase publication metadata
# ---------------------------------------------------------------------------
PODCAST_CONFIG: dict = {
    "title": "Anesis - Guided Meditations",
    "description": "Soothing guided meditations for daily life.",
    "language": "en-US",
    "author": "Anesis",
    "category": "Health & Fitness",
    "copyright": "© Anesis",
    "site_url": "https://your-podcast-site.com",
    "rss_filename": "rss.xml",
    "cover_filename": "cover.png",
}

SUPABASE_CONFIG: dict = {
    "bucket": "podcasts",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def setup_logging(level: str = "INFO") -> None:
    """Configure the root logger with a standard formatter."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def validate_config() -> None:
    """
    Validate critical configuration at startup.

    Raises:
        EnvironmentError: if OPENAI_API_KEY is absent.
    """
    logger = logging.getLogger(__name__)

    if not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. "
            "Add it to your .env file or export it as an environment variable."
        )

    if not os.path.exists(PATHS["theta_wave"]):
        logger.warning(
            "Theta wave file not found at '%s'. "
            "Generation will proceed without background music.",
            PATHS["theta_wave"],
        )
