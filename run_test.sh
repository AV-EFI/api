echo "*********************** Activating venv ***********************"
poetry install --no-dev 
poetry shell 

echo "*********************** Running pytest ***********************"
pytest tests/efi_endpoint.py