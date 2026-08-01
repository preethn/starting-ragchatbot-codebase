#!/bin/bash
# Check formatting without modifying files
set -e

cd "$(dirname "$0")/.."

echo "Checking black formatting..."
uv run black --check --diff backend main.py
