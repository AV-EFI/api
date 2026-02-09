#!/bin/sh
set -e

echo "*********************** Activating venv ***********************"
uv sync

echo "*********************** Starting FASTAPI ***********************"
echo "Swagger Documentation: http://127.0.0.1:8000/rest/v1/docs"
uv run uvicorn app.main:app --reload
