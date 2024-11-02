#!/bin/sh
set -e

echo "Install Poetry"
curl -sSL https://install.python-poetry.org | python3 -

echo "Check Poetry version"
poetry --version

echo "Starting installation and setup"
poetry install --no-dev

echo "Starting FASTAPI"
poetry run uvicorn efi_api.main:app --reload
