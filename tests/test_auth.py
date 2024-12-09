from fastapi.testclient import TestClient
from unittest.mock import patch
from datetime import datetime, timedelta
from efi_api.main import app
from efi_api.helpers.mock_auth import create_access_token

client = TestClient(app)

def test_authenticate_user_success():
    """Test successful authentication"""
    test_user_data = {
        "username": "test_user",
        "password": "correct_password"
    }
    
    mock_user_data = {
        "id": "123",
        "username": "test_user",
        "role": "user"
    }
    
    with patch('efi_api.routers.auth.mock_pid_system_auth', return_value=mock_user_data):
        response = client.post(
            "/av-efi/auth",
            data=test_user_data  # FastAPI will handle form data conversion
        )
        
        assert response.status_code == 200
        assert "access_token" in response.json()
        assert response.json()["token_type"] == "bearer"
        assert "expires_at" in response.json()

def test_authenticate_user_invalid_credentials():
    """Test authentication with invalid credentials"""
    test_user_data = {
        "username": "test_user",
        "password": "wrong_password"
    }
    
    with patch('efi_api.routers.auth.mock_pid_system_auth', return_value=None):
        response = client.post(
            "/av-efi/auth",
            data=test_user_data
        )
        
        assert response.status_code == 401
        assert response.json()["detail"] == "Incorrect username or password"

def test_protected_route_with_valid_token():
    """Test accessing protected route with valid token"""
    # Create a valid token
    test_user_data = {
        "id": "123",
        "username": "test_user",
        "role": "user"
    }
    token, _ = create_access_token(test_user_data)
    
    response = client.get(
        "/av-efi/protected",
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 200
    assert response.json()["message"] == "Access granted"
    assert response.json()["user"]["username"] == "test_user"

def test_protected_route_without_token():
    """Test accessing protected route without token"""
    response = client.get("/av-efi/protected")
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

def test_protected_route_with_invalid_token():
    """Test accessing protected route with invalid token"""
    response = client.get(
        "/av-efi/protected",
        headers={"Authorization": "Bearer invalid_token"}
    )
    
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authentication credentials" 