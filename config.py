# Meditation podcast creation program configuration

# OpenAI TTS parameters
OPENAI_TTS_CONFIG = {
    "voice": "fable",           # Neutral and clear voice (default)
    "model": "gpt-4o-mini-tts", # Advanced OpenAI TTS model
    "response_format": "wav",    # WAV output format for direct assembly
    "instructions_fr": "Tu es un professeur de méditation. Tu as un acent français. Parle tres doucement, en chuchotant, avec un ton apaisant et bienveillant. Rythme lent et posé.",
    "instructions_en": "You are a meditation teacher. You have a british accent and a clear english. Speak very softly, whispering, with a soothing and welcoming tone. Slow and steady rhythm.",
    "instructions_es": "Eres un profesor de meditación. Hablas espanol, estás murmurando y tienes un acento mexicano. Habla muy suavemente, con un tono acogedor y amigable. El ritmo es lento y estable.",
    "instructions_gr": "Είσαι ένας δάσκαλος μεθάνας. Μιλάς ελληνικά και έχεις αθηναϊκή προφορά. Φωνάζε πολύ πιο θαλάσσια, με χαλαρό τρόπο, με ένα πιο θαυμαστό και καλοπροαίρετο τρόπο. Το ρυθμό το κρατάς λίγο πιο πιντέντο.",
    # Language-specific voices (optional)
    "voices": {
        "fr": "fable",      # Neutral voice for French
        "en": "fable",      # Neutral voice for English  
        "es": "fable",      # Neutral voice for Spanish
        "gr": "nova"        # Warmer voice for Greek
    }
}

# LLM Configuration (disabled - no longer needed)
# LLM_CONFIG = {
#     "model": "gpt-4o-mini",     # Model for text generation
#     "enable_reformulation": False,  # Disable LLM reformulation to avoid language issues
#     # ... system prompts removed as unnecessary
# }

# Audio parameters
AUDIO_CONFIG = {
    "sample_rate": 44100,
    "background_volume": 0.95,  # Theta wave background music volume (95%)
    "tts_volume_boost": 1.2,    # TTS phrases amplification (120%)
    "save_wav": True,           # Also save as WAV (maximum quality)
    "save_mp3": True,           # Save as MP3 (compression for publication)
}

# File paths
PATHS = {
    "theta_wave": "data/theta_wave.wav",
    "database": "database/"
}

# Podcast and RSS/Supabase publication parameters
PODCAST_CONFIG = {
    "title": "Anesis - Guided Meditations",
    "description": "Soothing guided meditations for daily life.",
    "language": "en-US",
    "author": "Anesis",
    "category": "Health & Fitness",
    "copyright": "© Anesis",
    # Website or podcast homepage URL
    "site_url": "https://your-podcast-site.com",
    # RSS filename in the bucket
    "rss_filename": "rss.xml",
    "cover_filename": "cover.png",
}

SUPABASE_CONFIG = {
    # Public bucket name on Supabase side
    "bucket": "podcasts",
}

# (Optional) ElevenLabs parameters for existing code compatibility
ELEVENLABS_CONFIG = {
    "voice_id": "",
    "stability": 0.5,
    "similarity_boost": 0.5,
}
