#!/bin/sh
set -e

echo "*********************** Activating venv ***********************"
uv sync --no-python-downloads

echo "*********************** Running ruff **************************"
uv run ruff check
uv run ruff format

echo "*********************** Running pytest ************************"
if [ -n "${TEST_DATABASE_URL:-}" ]; then
    echo "Live PostgreSQL tests enabled via TEST_DATABASE_URL"
    DATABASE_URL="$TEST_DATABASE_URL" uv run alembic upgrade head
    uv run pytest
else
    echo "Skipping PostgreSQL tests; set TEST_DATABASE_URL to enable them"
    uv run pytest -m "not postgres"
fi
