from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_protected_route_without_token():
    """Test accessing protected route without token."""
    response = client.get("/auth/session")

    assert response.json() == {}
