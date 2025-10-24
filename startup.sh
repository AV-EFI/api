#!/bin/sh
set -e

echo "Install uv"
curl -LsSf https://astral.sh/uv/install.sh | sh

echo "Check uv version"
uv --version

echo "Starting installation and setup"
uv sync

echo "Starting FASTAPI"
uv run uvicorn app.main:app --reload
