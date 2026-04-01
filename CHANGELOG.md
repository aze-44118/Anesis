# Changelog

All notable changes to Anesis are documented here.

---

## [2.0.0] — 2026-04-01

### Added
- Full unit test suite (`tests/`) with 100% mocked API calls — runs on Python 3.9, 3.10, and 3.11
- GitHub Actions CI pipeline: lint, typecheck, and test jobs on every push
- `pyproject.toml` — package metadata, build config, and tool settings in one file
- `Makefile` — `make dev`, `make lint`, `make format`, `make typecheck`, `make test`, `make test-cov`
- `.pre-commit-config.yaml` — ruff, black, mypy, and standard hooks on every commit
- `audio_params.json` — runtime-tunable audio parameters (tone, speed, volume, theta\_volume)
- `anesis set` command to view and update audio parameters without editing files
- `anesis upload` command to publish an existing MP3 to Supabase
- `anesis batch` command to process an entire directory of scripts
- Exponential back-off retry logic on TTS API calls (tenacity, 3 attempts)
- Real-time progress bar via `tqdm`
- iTunes-compatible RSS 2.0 feed generation via Supabase
- Full type annotations across all public and private functions
- `.env.example` with documented environment variables

### Changed
- Rewrote audio assembly pipeline for correctness and testability
- Replaced all `print()` calls with structured `logging`
- Separated concerns: `main.py` (generation), `supabase_client.py` (storage/RSS), `config.py` (constants)
- Upgraded TTS model to `gpt-4o-mini-tts`
- MP3 export upgraded to 192 kbps with full ID3 tag support via `mutagen`
- Theta-wave mixing now includes a 3 s fade-in and fade-out with peak normalisation to 0.95

### Removed
- Standalone script with hardcoded paths
- Debug `print()` statements

---

## [1.0.0] — 2024-12-01

### Added
- Initial release: OpenAI TTS integration with theta-wave background mixing
- Single JSON script format (flat list)
- WAV and MP3 output to `database/`
- Basic Supabase upload support
