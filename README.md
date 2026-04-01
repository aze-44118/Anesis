# Anesis — AI Meditation Podcast Generator

[![Python](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/github/license/aze-44118/Anesis)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/aze-44118/Anesis/ci.yml?branch=main&label=CI)](https://github.com/aze-44118/Anesis/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

> **Anesis** *(Greek: ἄνεσις — relief, release, letting go)* is a command-line tool that transforms structured JSON meditation scripts into professional-grade podcast episodes using OpenAI TTS and theta-wave background music.

---

## What is Anesis?

Anesis automates the entire meditation podcast production pipeline — from raw text to a publish-ready MP3 with embedded metadata and an RSS feed — in a single command.

It uses OpenAI's `gpt-4o-mini-tts` model to synthesize each phrase of your script with a deep, measured meditation-guide voice, then layers the speech over a continuous theta-wave background, applies fade transitions, and publishes to Supabase with an iTunes-compatible RSS 2.0 feed.

```
JSON Script
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  extract_sentences()  →  phrase list + pause times  │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
          ┌────────────────────────────────┐
          │  OpenAI TTS (per phrase)       │
          │  · speed / tone / volume       │
          │  · tenacity retry (3 attempts) │
          └──────────────┬─────────────────┘
                         │
                         ▼
          ┌────────────────────────────────┐
          │  Audio Assembly                │
          │  · TTS phrases + silence gaps  │
          │  · 4 s theta-wave intro        │
          └──────────────┬─────────────────┘
                         │
                         ▼
          ┌────────────────────────────────┐
          │  mix_audio_with_background()   │
          │  · theta-wave full duration    │
          │  · 3 s fade-in / fade-out      │
          │  · peak normalisation → 0.95   │
          └──────────────┬─────────────────┘
                         │
                         ▼
          ┌────────────────────────────────┐
          │  Export                        │
          │  · WAV (44.1 kHz, lossless)    │
          │  · MP3 (192 kbps + ID3 tags)   │
          └──────────────┬─────────────────┘
                         │
                         ▼
          ┌────────────────────────────────┐
          │  Supabase (optional)           │
          │  · MP3 upload                  │
          │  · RSS 2.0 feed create/update  │
          └────────────────────────────────┘
```

---

## Features

- **OpenAI TTS integration** — uses `gpt-4o-mini-tts` with a configurable deep meditation-guide voice
- **Three JSON script formats** — flat list, single-key nested, or multi-session (weekly/daily series)
- **Custom pause durations** — each phrase carries its own silence interval
- **Theta-wave background mixing** — continuous background music with smooth fade-in/fade-out
- **Retry logic** — exponential back-off on TTS API errors (rate limits, timeouts, connection drops)
- **Progress bar** — real-time phrase generation progress via `tqdm`
- **High-quality MP3 encoding** — 192 kbps via `pydub` + ID3 tags (title, artist, cover art) via `mutagen`
- **Supabase publishing** — optional one-command upload with iTunes-compatible RSS feed generation
- **Batch processing** — generate an entire directory of scripts in one command
- **Structured logging** — no stray `print()` calls; full `logging` module integration
- **Type-annotated codebase** — all public and private functions carry type hints

---

## Quick Start

```bash
git clone https://github.com/aze-44118/Anesis.git
cd Anesis
chmod +x setup.sh && ./setup.sh
source venv/bin/activate
python main.py generate --t scripts/example_meditation_en.json --n "Morning Calm" --id daily
```

> **Prerequisites:** Python 3.9+, `ffmpeg` (for MP3 encoding), and an [OpenAI API key](https://platform.openai.com/api-keys).

---

## Installation

### Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.9+ |
| ffmpeg | any recent release |
| OpenAI API key | — |

### From source

```bash
# 1. Clone
git clone https://github.com/aze-44118/Anesis.git
cd Anesis

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Open .env and set OPENAI_API_KEY (and optionally SUPABASE_* variables)

# 5. Add the theta-wave audio file
# Place your theta_wave.wav (any sample rate) at data/theta_wave.wav
```

### Automated setup

The included `setup.sh` script handles steps 2–5 automatically:

```bash
chmod +x setup.sh && ./setup.sh
```

### Install as a package (optional)

```bash
pip install -e .
# Then run: anesis --help
```

---

## Configuration

### Environment variables

Copy `.env.example` to `.env` and set the variables below.

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Your OpenAI API key |
| `SUPABASE_URL` | No | Supabase project URL |
| `SUPABASE_SECRET_KEY` | No | Service role key (bypasses RLS — preferred) |
| `SUPABASE_PUBLISHABLE_KEY` | No | Anon key (fallback if secret key absent) |
| `SUPABASE_PODCAST_BUCKET` | No | Bucket name (default: `podcasts`) |
| `SUPABASE_COVER_URL` | No | Public URL of the podcast cover image |

### Audio parameters (`audio_params.json`)

Runtime audio tuning is stored in `audio_params.json` and editable via `anesis set`.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `tone` | `0.9` | Pitch coefficient (1.0 = neutral; < 1 = lower; > 1 = higher) |
| `speed` | `0.93` | TTS speed (0.25–4.0) |
| `volume` | `0.6` | Voice volume coefficient |
| `theta_volume` | `1.4` | Background music volume multiplier |

### TTS voice and instructions

Edit `config.py` to change:
- `OPENAI_TTS_CONFIG["voice"]` — OpenAI voice (default: `onyx`)
- `OPENAI_TTS_CONFIG["model"]` — TTS model (default: `gpt-4o-mini-tts`)
- `TTS_INSTRUCTION` — natural-language instruction that shapes the voice personality
- `PODCAST_CONFIG` — podcast title, author, description, category, and site URL

---

## Usage

### `anesis generate` — Generate a podcast

```bash
python main.py generate \
  --t scripts/morning_meditation.json \
  --n "Morning Calm — Session 1" \
  --id daily_meditations
```

| Argument | Description |
|----------|-------------|
| `--t PATH` | Path to the JSON script file (required) |
| `--n TITLE` | Episode title shown in the RSS feed (required) |
| `--id COLLECTION` | Supabase folder / collection name (required) |
| `--session KEY` | Session key for multi-session files (optional) |

### `anesis set` — View or update audio parameters

```bash
# View current parameters
python main.py set

# Update individual parameters
python main.py set --tone 1.05 --speed 0.9 --volume 0.7 --theta_volume 1.3
```

### `anesis upload` — Upload an existing MP3

```bash
python main.py upload \
  --file database/Morning_Calm.mp3 \
  --n "Morning Calm — Session 1" \
  --id daily_meditations
```

| Argument | Description |
|----------|-------------|
| `--file PATH` | MP3 path (relative to `database/` or absolute) |
| `--n TITLE` | Episode title (defaults to filename stem) |
| `--id COLLECTION` | Supabase folder / collection name |

### `anesis batch` — Process a directory of scripts

```bash
python main.py batch --dir scripts/ --id my_collection
```

| Argument | Description |
|----------|-------------|
| `--dir DIR` | Directory containing JSON script files |
| `--id COLLECTION` | Supabase folder / collection name |
| `--session KEY` | Session key applied to all multi-session files |

---

## JSON Script Format

Scripts are JSON files in one of three formats.

### Format 1 — Flat list

```json
[
  {
    "category": "induction",
    "text": "Take a comfortable position. Close your eyes.",
    "pause_after_sec": 8
  },
  {
    "category": "breathing",
    "text": "Inhale slowly for four counts. Exhale for six.",
    "pause_after_sec": 30
  },
  {
    "category": "exit",
    "text": "Gently return to the room. Open your eyes when ready.",
    "pause_after_sec": 5
  }
]
```

### Format 2 — Named session

```json
{
  "morning_calm": [
    { "category": "induction", "text": "...", "pause_after_sec": 8 }
  ]
}
```

### Format 3 — Multi-session

```json
{
  "day_1": [
    { "category": "induction", "text": "Welcome to day one.", "pause_after_sec": 5 }
  ],
  "day_2": [
    { "category": "induction", "text": "Welcome back for day two.", "pause_after_sec": 5 }
  ]
}
```

Use `--session day_2` to select a specific session.

### Supported categories

`induction` · `breathing` · `counting` · `silence` · `metaphor` · `autosuggestion` · `if-then` · `anchoring` · `exit` · `general` *(and any custom string)*

See [`scripts/example_meditation_en.json`](scripts/example_meditation_en.json) for a runnable example.

---

## Output

Generated files are saved to `database/`:

```
database/
├── Morning_Calm.wav    # Lossless master (44.1 kHz, float32)
└── Morning_Calm.mp3    # Distribution copy (192 kbps, ID3 tagged)
```

---

## Development

### Setup

```bash
make dev          # installs package in editable mode + dev extras + pre-commit hooks
make lint         # ruff + black --check
make format       # auto-fix with black and ruff
make typecheck    # mypy
make test         # pytest (no API key needed — all calls are mocked)
make test-cov     # pytest with coverage report
```

### Running the full pipeline locally

```bash
make generate-example   # requires a real OPENAI_API_KEY in .env
```

### Project structure

```
Anesis/
├── main.py               Core generator + CLI
├── config.py             Constants, logging, validation
├── supabase_client.py    Supabase storage + RSS
├── audio_params.json     Runtime audio tuning
├── data/                 theta_wave.wav, cover.png
├── database/             Generated audio output (gitignored)
├── scripts/              Example JSON meditation scripts
├── tests/                pytest test suite
├── reports/              Internal technical documentation
└── .github/              CI workflow + issue/PR templates
```

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for a full history of changes.

---

## License

Distributed under the [Apache License 2.0](LICENSE).
