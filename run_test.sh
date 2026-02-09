#!/bin/sh
set -e

echo "*********************** Activating venv ***********************"
uv sync

echo "*********************** Running ruff **************************"
uv run ruff check
uv run ruff format

echo "*********************** Running pytest ************************"
uv run pytest
