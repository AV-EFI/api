echo "*********************** Activating venv ***********************"
source venv/bin/activate
echo "*********************** Starting FASTAPI ***********************"
echo "Swagger Documentation: http://127.0.0.1:8000/docs"
uvicorn app.main:app --reload

