echo "Install Poetry"
curl -sSL https://install.python-poetry.org | python3 -

echo "Check Poetry version"
poetry --version

echo "Starting installation and setup"
poetry install --no-dev
poetry shell

echo "Starting FASTAPI"
uvicorn app.main:app --reload