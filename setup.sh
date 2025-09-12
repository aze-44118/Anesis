#!/bin/bash

echo "🚀 Meditation Podcast Generator Setup"
echo "====================================="

# Python verification
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed. Please install it first."
    exit 1
fi

echo "✅ Python 3 detected"

# Virtual environment creation
echo "📦 Creating virtual environment..."
python3 -m venv venv

# Virtual environment activation
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Dependencies installation
echo "📚 Installing dependencies..."
pip install -r requirements.txt

# .env file creation
if [ ! -f .env ]; then
    echo "🔑 Creating .env file..."
    cat > .env << EOF
# API keys configuration for podcast generator

# OpenAI API key (for TTS)
OPENAI_API_KEY=your_openai_api_key_here

# Supabase configuration (optional)
SUPABASE_URL=your_supabase_url_here
SUPABASE_ANON_KEY=your_supabase_anon_key_here
SUPABASE_SERVICE_ROLE_KEY=your_supabase_service_role_key_here
SUPABASE_COVER_URL=https://your-project.supabase.co/storage/v1/object/public/podcasts/cover.png
EOF
    echo "⚠️  Don't forget to configure your API keys in the .env file"
else
    echo "✅ .env file already exists"
fi

# Required audio files verification
echo "🎵 Verifying required audio files..."
required_files=("data/theta_wave.wav")
missing_files=()

for file in "${required_files[@]}"; do
    if [ ! -f "$file" ]; then
        missing_files+=("$file")
    fi
done

if [ ${#missing_files[@]} -eq 0 ]; then
    echo "✅ Required audio file present"
else
    echo "⚠️  Missing audio file:"
    for file in "${missing_files[@]}"; do
        echo "   - $file"
    done
    echo "   Please add a theta_wave.wav file in the data/ folder"
fi

echo ""
echo "🎉 Installation completed!"
echo ""
echo "📖 To get started:"
echo "   1. Configure your API keys in the .env file"
echo "   2. Add a theta_wave.wav file in the data/ folder"
echo "   3. Activate virtual environment: source venv/bin/activate"
echo "   4. Test with: python main.py generate --t scripts/sample_meditation.json --n test --id my_podcast"
echo ""
echo "📚 Check README.md for more information"
