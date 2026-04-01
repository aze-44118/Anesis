#!/usr/bin/env bash
# Anesis — Setup Script
# Bootstraps the Python virtual environment and validates the environment.

set -euo pipefail

echo "========================================"
echo "  Anesis — AI Meditation Podcast Setup  "
echo "========================================"
echo ""

# ---------------------------------------------------------------------------
# Python version check (>= 3.9 required)
# ---------------------------------------------------------------------------
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Please install Python 3.9 or later."
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"; then
    echo "[OK] Python $PYTHON_VERSION detected"
else
    echo "ERROR: Python 3.9+ required. Found: $PYTHON_VERSION"
    exit 1
fi

# ---------------------------------------------------------------------------
# Virtual environment
# ---------------------------------------------------------------------------
if [ ! -d "venv" ]; then
    echo "[..] Creating virtual environment..."
    python3 -m venv venv
    echo "[OK] Virtual environment created"
else
    echo "[OK] Virtual environment already exists"
fi

echo "[..] Activating virtual environment..."
# shellcheck disable=SC1091
source venv/bin/activate

# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------
echo "[..] Upgrading pip..."
pip install --upgrade pip --quiet

echo "[..] Installing dependencies..."
pip install -r requirements.txt --quiet
echo "[OK] Dependencies installed"

# ---------------------------------------------------------------------------
# ffmpeg check (required by pydub for MP3 encoding)
# ---------------------------------------------------------------------------
if command -v ffmpeg &>/dev/null; then
    echo "[OK] ffmpeg detected — MP3 encoding enabled"
else
    echo ""
    echo "[WARN] ffmpeg not found. MP3 encoding requires ffmpeg."
    echo "       Install it with:"
    echo "         macOS:          brew install ffmpeg"
    echo "         Debian/Ubuntu:  sudo apt install ffmpeg"
    echo "         Windows:        https://ffmpeg.org/download.html"
    echo ""
fi

# ---------------------------------------------------------------------------
# .env file
# ---------------------------------------------------------------------------
if [ ! -f .env ]; then
    echo "[..] Creating .env from .env.example..."
    cp .env.example .env
    echo "[OK] .env created — edit it and add your API keys before running Anesis"
else
    echo "[OK] .env already exists"
fi

# ---------------------------------------------------------------------------
# Required audio files
# ---------------------------------------------------------------------------
echo "[..] Checking required audio files..."
if [ -f "data/theta_wave.wav" ]; then
    echo "[OK] data/theta_wave.wav present"
else
    echo "[WARN] data/theta_wave.wav not found."
    echo "       Place a theta-wave audio file at data/theta_wave.wav before generating podcasts."
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo "========================================"
echo "  Setup complete!"
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your OPENAI_API_KEY"
echo "  2. Place data/theta_wave.wav in the data/ folder"
echo "  3. Activate the environment: source venv/bin/activate"
echo "  4. Generate a sample:        python main.py generate \\"
echo "       --t scripts/sample_meditation_fr.json \\"
echo "       --n \"My First Meditation\" --id my_collection"
echo ""
echo "See README.md for the full CLI reference and JSON script format."
