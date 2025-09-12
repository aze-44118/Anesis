# Meditation Podcast Generator

A CLI tool for automatically creating meditation podcasts from JSON scripts using OpenAI TTS and background music.

## Features

- **Automatic TTS** : Text-to-speech conversion using OpenAI TTS with natural, soothing voices
- **Smart Audio Assembly** : Automatic combination of TTS phrases with custom pauses and background music
- **Custom Pauses** : Each phrase can have its own pause duration (advanced JSON format)
- **Continuous Background Music** : Theta wave background music throughout the entire duration
- **Multi-language Support** : Automatic language detection and appropriate voice selection
- **Supabase Integration** : Optional podcast publishing with RSS feed generation

## Installation

### Quick Setup
```bash
git clone <repository>
cd Anesis
chmod +x setup.sh
./setup.sh
```

### Manual Setup

1. **Clone the repository**
```bash
git clone <repository>
cd Anesis
```

2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure API keys**
```bash
cp .env.example .env
# Edit .env with your API keys
```

5. **Add required audio files**
Place a `theta_wave.wav` file in the `data/` directory for background music.

## Usage

### Basic Command
```bash
python main.py generate --t "path/to/script.json" --n "podcast_name" --id "collection_id"
```

### Arguments
- `--t` or `--text` : Path to JSON script file (required)
- `--n` or `--name` : Episode title for the podcast (required)
- `--id` : Collection/folder ID for organizing podcasts in Supabase (required)
- `--session` : Session name for multi-session JSON files (optional)

### Examples

**Basic meditation generation:**
```bash
python main.py generate --t "scripts/sample_meditation.json" --n "Morning Meditation" --id "daily_meditations"
```

**Multi-session weekly meditation:**
```bash
python main.py generate --t "scripts/weekly_meditations.json" --n "Week 1 - Focus" --id "weekly_series" --session "day_1"
```

## JSON Script Format

The tool uses a structured JSON format with custom pause durations:

```json
[
  {
    "category": "induction",
    "text": "Take a comfortable position. Close your eyes. Breathe deeply.",
    "pause_after_sec": 8
  },
  {
    "category": "breathing",
    "text": "Inhale for four counts, exhale for six counts.",
    "pause_after_sec": 30
  },
  {
    "category": "silence",
    "text": "Enjoy this moment of tranquility.",
    "pause_after_sec": 90
  }
]
```

### Supported Categories
- `induction` - Opening and setup
- `breathing` - Breathing exercises
- `counting` - Countdown or counting exercises
- `silence` - Quiet reflection periods
- `metaphor` - Guided imagery
- `autosuggestion` - Positive affirmations
- `if-then` - Conditional guidance
- `anchoring` - Closing anchor phrases
- `exit` - Ending and return to awareness

## Configuration

Edit `config.py` to customize:
- TTS parameters (voice, language, speed)
- Audio settings (sample rate, volume levels)
- Podcast metadata (title, description, author)
- File output formats (WAV, MP3)

## Environment Variables

Create a `.env` file with the following variables:

```env
# Required
OPENAI_API_KEY=your_openai_api_key_here

# Optional - Supabase Integration
SUPABASE_URL=your_supabase_url_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here
SUPABASE_COVER_URL=https://your-project.supabase.co/storage/v1/object/public/podcasts/cover.png
```

## Output Files

Generated podcasts are saved in the `database/` directory with both WAV (high quality) and MP3 (compressed) formats.

## Multi-language Support

The tool automatically detects language from filename suffixes:
- `_en.json` - English
- `_fr.json` - French  
- `_es.json` - Spanish
- `_gr.json` - Greek

## Dependencies

- **librosa** : Audio processing
- **soundfile** : Audio file I/O
- **numpy** : Numerical computations
- **openai** : OpenAI TTS API
- **requests** : HTTP requests
- **supabase** : Database and storage integration
- **python-dotenv** : Environment variable management

## Features

- High-quality OpenAI TTS with multiple voice options
- Advanced JSON format with custom pause durations
- Automatic language detection and voice selection
- Background music mixing with theta waves
- Optional Supabase integration for podcast hosting
- RSS feed generation for podcast distribution
- Multi-session support for weekly/daily meditation series

## License

This project is open source. Please ensure you have proper API keys and follow OpenAI's usage policies.

## Contributing

Feel free to submit issues and enhancement requests!
