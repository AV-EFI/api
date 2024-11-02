#!/bin/sh
set -e

echo "*********************** Activating venv ***********************"
poetry install

echo "*********************** Starting FASTAPI ***********************"
echo "Swagger Documentation: http://127.0.0.1:8000/docs"
poetry run uvicorn efi_api.main:app --reload
