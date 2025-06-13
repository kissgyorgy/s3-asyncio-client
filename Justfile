# Show available commands
help:
    @just --list

# Install dependencies
install:
    uv sync

test args:
    python -m pytest {{ args}}

lint:
    ruff check --fix src/ tests/

format:
    ruff format src/ tests/

# Run all quality checks
check: lint format test

# Build documentation
docs-build:
    mkdocs build

# Serve documentation locally
docs-serve:
    mkdocs serve

# Clean temporary files
clean:
    find . -type d -name "__pycache__" -exec rm -rf {} +
    find . -type f -name "*.pyc" -delete
    rm -rf .pytest_cache
