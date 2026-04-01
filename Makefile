.PHONY: install dev lint format typecheck test test-cov clean generate-example

# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

install:
	pip install -e .

dev:
	pip install -e ".[dev]"
	pre-commit install

# ---------------------------------------------------------------------------
# Code quality
# ---------------------------------------------------------------------------

lint:
	ruff check .
	black --check .

format:
	black .
	ruff check --fix .

typecheck:
	mypy main.py config.py supabase_client.py

# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=. --cov-report=term-missing --cov-report=xml

# ---------------------------------------------------------------------------
# Housekeeping
# ---------------------------------------------------------------------------

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build *.egg-info

# ---------------------------------------------------------------------------
# Quick smoke test (requires real API key)
# ---------------------------------------------------------------------------

generate-example:
	python main.py generate \
		--t scripts/sample_meditation_fr.json \
		--n "Sample Meditation" \
		--id test_collection
