from fastapi.testclient import TestClient
from efi_api.main import app, EFI_PATH

client = TestClient(app)

def test_protected_route_without_token():
    """Test accessing protected route without token"""
    response = client.get(f"/auth/session")
    
    assert response.json() == {}
