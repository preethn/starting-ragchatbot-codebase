#!/bin/bash
# Run all quality checks: formatting check + tests
set -e

cd "$(dirname "$0")/.."

echo "Checking black formatting..."
uv run black --check --diff backend main.py

echo "Running tests..."
cd backend && uv run pytest
