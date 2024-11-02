#!/bin/sh
set -e

echo "*********************** Activating venv ***********************"
poetry install

echo "*********************** Running pytest ***********************"
poetry run pytest
