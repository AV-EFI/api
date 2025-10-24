#!/bin/sh
set -e

echo "*********************** Activating venv ***********************"
uv sync

echo "*********************** Running pytest ***********************"
uv run pytest
