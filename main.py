#!/usr/bin/env python3
"""
Meditation podcast creation program
Controlled via CLI with the 'generate' command
"""

import argparse
import os
import re
from pathlib import Path
from typing import List
import tempfile
import datetime
from email.utils import formatdate
import xml.etree.ElementTree as ET

# Imports for audio processing
import soundfile as sf
import numpy as np

# Imports for TTS
import requests
import openai

# Configuration
from config import OPENAI_TTS_CONFIG, AUDIO_CONFIG, PATHS, PODCAST_CONFIG, SUPABASE_CONFIG, ELEVENLABS_CONFIG
from supabase_client import SupabasePublisher


class MeditationPodcastGenerator:
    def __init__(self):
        # OpenAI TTS initialization
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found in .env")
        
        openai.api_key = api_key
        print(f"✓ OpenAI TTS initialized with voice {OPENAI_TTS_CONFIG['voice']}")

        # Supabase initialization (dedicated client)
        self.publisher = SupabasePublisher()
        if self.publisher.is_enabled():
            print("✓ Supabase initialized")
    
    def _detect_language_from_filename(self, file_path: str) -> str:
        """Detects language based on JSON filename"""
        filename = os.path.basename(file_path).lower()
        
        if filename.endswith('_en.json'):
            return 'en'
        elif filename.endswith('_fr.json'):
            return 'fr'
        elif filename.endswith('_es.json'):
            return 'es'
        elif filename.endswith('_gr.json'):
            return 'gr'
        else:
            # By default, use French
            return 'fr'
    
    def extract_sentences(self, file_path: str, session_name: str = None) -> dict:
        """Extracts sentences from JSON file with custom pauses"""
        import json
        
        if file_path.endswith('.json'):
            # JSON file reading
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Automatic language detection based on filename
            detected_language = self._detect_language_from_filename(file_path)
            print(f"🌍 Language detected: {detected_language}")
            if detected_language == 'gr':
                print(f"🇬🇷 Greek file detected - Full support activated")
            
            # Format detection: direct list or nested with key
            sentences_with_pauses = []
            podcast_key = None
            
            if isinstance(data, list):
                # Direct format: list of objects
                sentences_with_pauses = []
                for item in data:
                    if isinstance(item, dict) and 'text' in item and 'pause_after_sec' in item:
                        sentences_with_pauses.append({
                            'text': item['text'],
                            'pause_after_sec': item['pause_after_sec'],
                            'category': item.get('category', 'general')
                        })
                podcast_key = "podcast"
            elif isinstance(data, dict):
                if len(data) == 1:
                    # Nested format: single key containing the list
                    podcast_key = list(data.keys())[0]
                    inner_data = data[podcast_key]
                    
                    if isinstance(inner_data, list):
                        for item in inner_data:
                            if isinstance(item, dict) and 'text' in item and 'pause_after_sec' in item:
                                sentences_with_pauses.append({
                                    'text': item['text'],
                                    'pause_after_sec': item['pause_after_sec'],
                                    'category': item.get('category', 'general')
                                })
                    else:
                        raise ValueError(f"Invalid JSON format. Key '{podcast_key}' must contain a list")
                elif len(data) > 1:
                    # Multi-session format (ex: weekly_en.json with 7 days)
                    available_sessions = list(data.keys())
                    print(f"📅 Multi-session file detected with {len(available_sessions)} available sessions:")
                    for i, session in enumerate(available_sessions, 1):
                        print(f"   {i}. {session}")
                    
                    # Session selection
                    if session_name and session_name in available_sessions:
                        podcast_key = session_name
                        print(f"🎯 Specified session: {podcast_key}")
                    else:
                        if session_name:
                            print(f"⚠️  Session '{session_name}' not found, using first session")
                        podcast_key = available_sessions[0]
                        print(f"🎯 Default selected session: {podcast_key}")
                    
                    inner_data = data[podcast_key]
                    if isinstance(inner_data, list):
                        for item in inner_data:
                            if isinstance(item, dict) and 'text' in item and 'pause_after_sec' in item:
                                sentences_with_pauses.append({
                                    'text': item['text'],
                                    'pause_after_sec': item['pause_after_sec'],
                                    'category': item.get('category', 'general')
                                })
                    else:
                        raise ValueError(f"Invalid JSON format. Session '{podcast_key}' must contain a list")
                else:
                    raise ValueError("Invalid JSON format. Empty object")
            else:
                raise ValueError("Invalid JSON format. Expected: list of objects or object with keys containing lists")
            
            if not sentences_with_pauses:
                raise ValueError("No valid sentences found in JSON")
            
            print(f"Extracted {len(sentences_with_pauses)} sentences with custom pauses")
            print(f"Detected podcast key: {podcast_key}")
            
            return {
                'sentences_with_pauses': sentences_with_pauses,
                'podcast_key': podcast_key,
                'detected_language': detected_language
            }
        else:
            raise ValueError("Only JSON files are supported")
    
    def generate_tts_audio(self, text: str, language: str = 'fr') -> np.ndarray:
        """Generates TTS audio for a given phrase with the specified language"""
        return self._generate_openai_tts_audio(text, language)
    
    def _generate_openai_tts_audio(self, text: str, language: str = 'fr') -> np.ndarray:
        """Generates audio with OpenAI TTS directly from script text"""
        print(f"    🔧 TTS configuration loaded:")
        print(f"       - Model: {OPENAI_TTS_CONFIG['model']}")
        print(f"       - Voice: {OPENAI_TTS_CONFIG['voice']}")
        print(f"       - Format: {OPENAI_TTS_CONFIG['response_format']}")
        
        try:
            # Input text verification
            if not text or len(text.strip()) == 0:
                print(f"    ⚠️  Empty text detected, returning silence")
                return self.create_silence(2.0)
            
            print(f"    📝 Text to process: '{text[:50]}...'")
            
            # Direct audio generation with configured TTS model
            print(f"    🎵 Audio generation with {OPENAI_TTS_CONFIG['model']}...")
            print(f"    🔑 TTS model used: {OPENAI_TTS_CONFIG['model']}")
            print(f"    🎭 Voice used: {OPENAI_TTS_CONFIG['voice']}")
            
            # Instruction selection based on detected language
            if language == 'en':
                tts_instructions = OPENAI_TTS_CONFIG["instructions_en"]
                print(f"    🌍 English TTS instructions selected")
            elif language == 'es':
                tts_instructions = OPENAI_TTS_CONFIG["instructions_es"]
                print(f"    🌍 Spanish TTS instructions selected")
            elif language == 'gr':
                tts_instructions = OPENAI_TTS_CONFIG["instructions_gr"]
                print(f"    🌍 Greek TTS instructions selected")
            else:
                tts_instructions = OPENAI_TTS_CONFIG["instructions_fr"]
                print(f"    🌍 French TTS instructions selected")
            
            # Voice selection based on language
            voice_to_use = OPENAI_TTS_CONFIG["voice"]  # Default voice
            if "voices" in OPENAI_TTS_CONFIG and language in OPENAI_TTS_CONFIG["voices"]:
                voice_to_use = OPENAI_TTS_CONFIG["voices"][language]
                print(f"    🎭 Specific voice for {language}: {voice_to_use}")
            else:
                print(f"    🎭 Default voice: {voice_to_use}")
            
            print(f"    🔧 TTS parameters: voice={voice_to_use}, format={OPENAI_TTS_CONFIG['response_format']}")
            
            # TTS generation with original script text
            response = openai.audio.speech.create(
                model=OPENAI_TTS_CONFIG["model"],
                voice=voice_to_use,
                input=text,  # Original JSON script text
                response_format=OPENAI_TTS_CONFIG["response_format"],
                instructions=tts_instructions,
                timeout=60  # 60 second timeout for TTS
            )
            
            print(f"    ✅ TTS response received, size: {len(response.content)} bytes")
            
            # Temporary save and loading with librosa
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                tmp_file.write(response.content)
                tmp_path = tmp_file.name
                print(f"    💾 Temporary WAV file created: {tmp_path}")
            
            try:
                # Loading with soundfile - faster and more stable
                print(f"    🔄 Loading WAV with soundfile...")
                audio, sr = sf.read(tmp_path, dtype='float32')
                print(f"    📊 WAV audio loaded: {len(audio)} samples, SR: {sr}")
                
                # Resample if necessary
                if sr != AUDIO_CONFIG["sample_rate"]:
                    print(f"    🔄 Resample from {sr}Hz to {AUDIO_CONFIG['sample_rate']}Hz...")
                    ratio = AUDIO_CONFIG["sample_rate"] / sr
                    new_length = int(len(audio) * ratio)
                    audio = np.interp(np.linspace(0, len(audio), new_length), np.arange(len(audio)), audio)
                    print(f"    📊 Resample completed: {len(audio)} samples")
                
                # Apply volume boost for TTS phrases
                audio = audio * AUDIO_CONFIG["tts_volume_boost"]
                print(f"    🔊 Volume boost applied: x{AUDIO_CONFIG['tts_volume_boost']}")
                
                # Verify that audio is not empty or silent
                if len(audio) == 0 or np.max(np.abs(audio)) < 0.001:
                    print(f"    ⚠️  Generated audio too weak or empty, returning silence")
                    return self.create_silence(2.0)
                
                print(f"    ✅ TTS WAV audio generated successfully: {len(audio)} samples, max: {np.max(np.abs(audio)):.4f}")
                return audio
                
            except Exception as soundfile_error:
                print(f"    ⚠️  Soundfile error: {soundfile_error}")
                # Fallback: silence in case of loading error
                return self.create_silence(2.0)
            finally:
                # Temporary file cleanup
                try:
                    os.unlink(tmp_path)
                    print(f"    🗑️  Temporary WAV file deleted")
                except:
                    pass  # Ignore deletion errors
                    
        except Exception as e:
            print(f"    ❌ OpenAI TTS error: {e}")
            print(f"    📋 Error details: {type(e).__name__}")
            # Fallback: silence in case of TTS error
            return self.create_silence(2.0)
    
    def create_silence(self, duration: float) -> np.ndarray:
        """Creates silence of given duration"""
        try:
            samples = int(duration * AUDIO_CONFIG["sample_rate"])
            silence = np.zeros(samples, dtype=np.float32)  # Using float32 to save memory
            print(f"    🔇 Silence created: {len(silence)} samples ({duration}s)")
            return silence
        except Exception as e:
            print(f"    ⚠️  Silence creation error: {e}")
            # Ultra-simple fallback: return empty array
            return np.array([], dtype=np.float32)
    
    def load_audio_file(self, file_path: str) -> np.ndarray:
        """Loads an audio file with soundfile"""
        try:
            print(f"🔍 DEBUG load_audio_file: Starting load {file_path}")
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Audio file not found: {file_path}")
            
            print(f"🔍 DEBUG load_audio_file: File exists, starting soundfile.read...")
            # Loading with soundfile - faster and more stable
            audio, sr = sf.read(file_path, dtype='float32')
            print(f"🔍 DEBUG load_audio_file: soundfile.read successful, audio: {len(audio)} samples, sr: {sr}")
            
            # Limit to 40 minutes if necessary
            max_duration = 40 * 60  # 40 minutes in seconds
            if len(audio) > max_duration * sr:
                audio = audio[:max_duration * sr]
                print(f"🔍 DEBUG load_audio_file: Duration limited to 40min: {len(audio)/sr:.1f}s")
            else:
                print(f"🔍 DEBUG load_audio_file: Duration loaded: {len(audio)/sr:.1f}s")
            
            # Resample if necessary
            if sr != AUDIO_CONFIG["sample_rate"]:
                print(f"🔍 DEBUG load_audio_file: Resample from {sr}Hz to {AUDIO_CONFIG['sample_rate']}Hz...")
                # Simple resample with numpy (approximate but fast)
                ratio = AUDIO_CONFIG["sample_rate"] / sr
                new_length = int(len(audio) * ratio)
                audio = np.interp(np.linspace(0, len(audio), new_length), np.arange(len(audio)), audio)
                print(f"🔍 DEBUG load_audio_file: Resample completed: {len(audio)} samples")
            
            print(f"🔍 DEBUG load_audio_file: Loading completed successfully")
            return audio
            
        except Exception as e:
            print(f"    ❌ Audio loading error '{file_path}': {e}")
            print(f"🔍 DEBUG load_audio_file: Error type: {type(e).__name__}")
            print(f"🔍 DEBUG load_audio_file: Details: {str(e)}")
            # Fallback: return 1 second silence
            return self.create_silence(1.0)
    
    def mix_audio_with_background(self, foreground: np.ndarray, background: np.ndarray) -> np.ndarray:
        """Mixes main audio with background music"""
        try:
            # Input verification
            if len(foreground) == 0 or len(background) == 0:
                print("  ⚠️  Empty audio detected, returning main content")
                return foreground
            
            # Calculate target duration: content + 1 minute of background music
            target_duration = len(foreground) + int(60 * AUDIO_CONFIG["sample_rate"])  # +1 minute
            
            # Limit background music duration to target duration
            if len(background) > target_duration:
                background = background[:target_duration]
                print(f"  ✓ Background music limited to {target_duration/AUDIO_CONFIG['sample_rate']:.1f}s")
            
            # Repeat background music if necessary to cover target duration
            if len(background) < target_duration:
                repeats = int(np.ceil(target_duration / len(background))) + 1
                background = np.tile(background, repeats)
                print(f"  ✓ Background music repeated {repeats}x to cover {target_duration/AUDIO_CONFIG['sample_rate']:.1f}s")
            
            # Cut background to exact target duration
            background = background[:target_duration]
            
            # Extend foreground with silence to match target duration
            if len(foreground) < target_duration:
                silence_duration = target_duration - len(foreground)
                silence = np.zeros(silence_duration, dtype=np.float32)
                foreground = np.concatenate([foreground, silence])
                print(f"  ✓ Content extended with {silence_duration/AUDIO_CONFIG['sample_rate']:.1f}s of silence")
            
            # Background music preparation with adjusted volume
            background_audio = background * AUDIO_CONFIG["background_volume"]
            
            # Simple mix: content + background music
            mixed = foreground + background_audio
            
            # Final normalization if necessary
            if np.max(np.abs(mixed)) > 1.0:
                mixed = mixed / np.max(np.abs(mixed)) * 0.98
                print(f"  Normalization applied")
            
            return mixed
            
        except Exception as e:
            print(f"  ⚠️  Audio mixing error: {e}")
            # Fallback: return main content without mixing
            return foreground

    def generate_podcast(self, file_path: str, episode_title: str, user_id: str, session_name: str = None):
        """Generates the complete podcast with the new format"""
        print(f"🎬 Podcast generation: {episode_title}")
        
        # Sentence extraction (JSON with custom pauses)
        sentences_data = self.extract_sentences(file_path, session_name)
        
        # File name and episode title determination
        if session_name:
            # Use session name for file, title for display
            file_name = session_name
            podcast_title = episode_title
            print(f"📁 File name: {file_name}")
            print(f"📻 Episode title: {podcast_title}")
        else:
            # Fallback: use title as file name
            file_name = episode_title.replace(" ", "_").replace("-", "_")
            podcast_title = episode_title
            print(f"📁 Generated file name: {file_name}")
            print(f"📻 Episode title: {podcast_title}")
        
        # Retrieved detected language
        detected_language = sentences_data.get('detected_language', 'fr')
        print(f"🌍 Podcast language: {detected_language}")
        print(f"🔍 DEBUG: Starting theta_wave loading...")
        
        # Theta wave background music loading
        try:
            print(f"🔍 DEBUG: Theta wave path: {PATHS['theta_wave']}")
            print(f"🔍 DEBUG: File exists: {os.path.exists(PATHS['theta_wave'])}")
            theta_wave = self.load_audio_file(PATHS["theta_wave"])
            print("✓ Theta wave background music loaded")
            print(f"🔍 DEBUG: Theta wave size: {len(theta_wave)} samples")
        except Exception as e:
            print(f"⚠️  Theta wave loading error: {e}")
            print(f"🔍 DEBUG: Error type: {type(e).__name__}")
            print(f"🔍 DEBUG: Details: {str(e)}")
            print("   Generation without background music...")
            theta_wave = None
        
        # Processing format with custom pauses
        print(f"Processing format with {len(sentences_data['sentences_with_pauses'])} sentences...")
        
        # Data size verification to avoid memory issues
        max_phrases = 50  # Safety limit
        if len(sentences_data['sentences_with_pauses']) > max_phrases:
            print(f"⚠️  High number of sentences ({len(sentences_data['sentences_with_pauses'])}), batch processing...")
            # Batch processing to avoid memory issues
            sentences_to_process = sentences_data['sentences_with_pauses'][:max_phrases]
        else:
            sentences_to_process = sentences_data['sentences_with_pauses']
        
        # TTS generation for each sentence
        phrase_audios = []
        total_tts_seconds = 0.0
        total_pause_seconds = 0.0
        
        for i, phrase_data in enumerate(sentences_to_process):
            text = phrase_data['text']
            pause_duration = phrase_data['pause_after_sec']
            category = phrase_data['category']
            
            print(f"  Sentence {i+1}/{len(sentences_to_process)} [{category}]: {text[:50]}...")
            
            # TTS audio generation with detected language
            audio = self.generate_tts_audio(text, detected_language)
            
            # Generated audio verification
            if len(audio) > 0:
                print(f"    ✅ TTS audio added: {len(audio)} samples")
                phrase_audios.append(audio)
                
                # TTS duration calculation
                tts_duration = len(audio) / AUDIO_CONFIG["sample_rate"]
                total_tts_seconds += tts_duration
                print(f"    ⏱️  TTS duration: {tts_duration:.2f}s")
            else:
                print(f"    ⚠️  Empty TTS audio, ignored")
                # Add silence instead
                silence_audio = self.create_silence(2.0)
                phrase_audios.append(silence_audio)
                total_tts_seconds += 2.0
            
            # Custom pause creation
            if i < len(sentences_to_process) - 1:  # No pause after last sentence
                pause_audio = self.create_silence(pause_duration)
                phrase_audios.append(pause_audio)
                total_pause_seconds += pause_duration
        
        # Final assembly: all sentences + pauses
        if phrase_audios:
            try:
                final_audio = np.concatenate(phrase_audios)
            except Exception as e:
                print(f"  ⚠️  Audio assembly error: {e}")
                # Fallback: create 5 second silence
                final_audio = self.create_silence(5.0)
        else:
            final_audio = np.array([], dtype=np.float32)
        
        # Add 4 seconds of theta wave before podcast start
        if theta_wave is not None and len(final_audio) > 0:
            try:
                intro_theta_samples = int(4.0 * AUDIO_CONFIG["sample_rate"])
                intro_theta = theta_wave[:intro_theta_samples]
                final_audio = np.concatenate([intro_theta, final_audio])
                print(f"  ✓ 4 seconds of theta wave added at the beginning")
            except Exception as e:
                print(f"  ⚠️  Theta wave addition error: {e}")
                # Keep original audio without intro
        else:
            print("  ⚠️  No theta wave available for introduction")
        
        # Total duration calculation (after intro addition)
        total_duration = len(final_audio) / AUDIO_CONFIG["sample_rate"]
        
        print(f"✓ Podcast assembled: {len(phrase_audios)} audio segments")
        if len(sentences_data['sentences_with_pauses']) > max_phrases:
            print(f"⚠️  Processed {len(sentences_to_process)} sentences out of {len(sentences_data['sentences_with_pauses'])} (safety limit)")
        print(f"📊 Audio statistics:")
        print(f"   • Generated TTS duration: {total_tts_seconds:.1f}s")
        print(f"   • Pause duration: {total_pause_seconds:.1f}s")
        print(f"   • Total duration: {total_duration:.1f}s")
        
        # Mix with theta wave background music on all content (if available)
        if theta_wave is not None:
            print(f"   🎵 Mixing with theta wave background music...")
            print(f"   📊 Main audio: {len(final_audio)} samples, max: {np.max(np.abs(final_audio)):.4f}")
            print(f"   📊 Background music: {len(theta_wave)} samples, max: {np.max(np.abs(theta_wave)):.4f}")
            
            final_audio = self.mix_audio_with_background(final_audio, theta_wave)
            print(f"   ✅ Mixing completed: {len(final_audio)} samples, max: {np.max(np.abs(final_audio)):.4f}")
        else:
            print("   No background music applied")
        
        # Save as WAV first (maximum quality)
        output_path = None
        if AUDIO_CONFIG["save_wav"]:
            wav_output_path = os.path.join(PATHS["database"], f"{file_name}.wav")
            try:
                sf.write(wav_output_path, final_audio, AUDIO_CONFIG["sample_rate"])
                print(f"✓ Podcast WAV generated successfully: {wav_output_path}")
                # Use WAV as main file if MP3 is not requested
                if not AUDIO_CONFIG["save_mp3"]:
                    output_path = wav_output_path
            except Exception as e:
                print(f"❌ WAV save error: {e}")
                # Attempt to save with alternative name
                fallback_wav_path = os.path.join(PATHS["database"], f"{file_name}_fallback.wav")
                try:
                    sf.write(fallback_wav_path, final_audio, AUDIO_CONFIG["sample_rate"])
                    print(f"✓ WAV backup save: {fallback_wav_path}")
                    wav_output_path = fallback_wav_path
                    if not AUDIO_CONFIG["save_mp3"]:
                        output_path = wav_output_path
                except Exception as e2:
                    print(f"❌ WAV backup save failed: {e2}")
                    if not AUDIO_CONFIG["save_mp3"]:
                        raise Exception("Unable to save podcast WAV")
        
        # Convert to MP3 for publication (final compression)
        if AUDIO_CONFIG["save_mp3"]:
            mp3_output_path = os.path.join(PATHS["database"], f"{file_name}.mp3")
            try:
                print(f"🔄 Final WAV → MP3 conversion...")
                # Using soundfile for conversion
                sf.write(mp3_output_path, final_audio, AUDIO_CONFIG["sample_rate"], format='MP3')
                print(f"✓ Podcast MP3 generated successfully: {mp3_output_path}")
                output_path = mp3_output_path
            except Exception as e:
                print(f"❌ MP3 conversion error: {e}")
                # Attempt to save with alternative name
                fallback_mp3_path = os.path.join(PATHS["database"], f"{file_name}_fallback.mp3")
                try:
                    sf.write(fallback_mp3_path, final_audio, AUDIO_CONFIG["sample_rate"], format='MP3')
                    print(f"✓ MP3 backup save: {fallback_mp3_path}")
                    output_path = fallback_mp3_path
                except Exception as e2:
                    print(f"❌ MP3 backup conversion failed: {e2}")
                    # Keep WAV if MP3 conversion fails
                    if AUDIO_CONFIG["save_wav"] and 'wav_output_path' in locals():
                        output_path = wav_output_path
                        print(f"⚠️  Using WAV file: {output_path}")
                    else:
                        raise Exception("Unable to save podcast")
        
        # Verify we have an output file
        if output_path is None:
            raise Exception("No output format configured (WAV and MP3 disabled)")

        # Supabase publication (MP3 upload + RSS)
        if self.publisher.is_enabled():
            try:
                print("[Publish] Starting Supabase publication…")
                mp3_url, rss_url = self.publisher.publish_episode(output_path, file_name, total_duration, podcast_title, user_id)
                if mp3_url and rss_url:
                    print(f"[Publish] ✓ Publication successful. RSS: {rss_url}")
                else:
                    print("[Publish] ⚠️  Publication not performed (client disabled or missing URLs)")
            except Exception as e:
                print(f"⚠️  Supabase publication failed: {e}")

        return output_path


def main():
    parser = argparse.ArgumentParser(description="Meditation podcast generator")
    parser.add_argument("generate", help="Generation command")
    parser.add_argument("--t", "--text", required=True, help="Path to JSON script file")
    parser.add_argument("--n", "--name", required=True, help="Episode title (displayed in RSS)")
    parser.add_argument("--id", required=True, help="Collection/folder name to organize podcasts in Supabase")
    parser.add_argument("--session", help="Session name for MP3 file (ex: day_1_detox_hooks)")

    args = parser.parse_args()
    
    if args.generate != "generate":
        print("Invalid command. Use 'generate'")
        return
    
    # Required files verification
    required_files = [PATHS["theta_wave"]]  # Only theta_wave is required
    
    # Required files verification
    for file_path in required_files:
        if not os.path.exists(file_path):
            print(f"Required file missing: {file_path}")
            return
    
    # JSON file verification
    if not os.path.exists(args.t):
        print(f"JSON file not found: {args.t}")
        return
    
    if not args.t.endswith('.json'):
        print("Error: Only JSON files are supported")
        return
    
    print("✓ Format detected: new format with custom pauses (OpenAI TTS + theta_wave)")
    
    # Generator creation
    generator = MeditationPodcastGenerator()
    
    # Podcast generation
    try:
        generator.generate_podcast(args.t, args.n, args.id, args.session)
    except Exception as e:
        print(f"Error during generation: {e}")


if __name__ == "__main__":
    main()
