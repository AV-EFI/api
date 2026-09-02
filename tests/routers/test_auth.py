from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_protected_route_without_token():
    """Test accessing protected route without token."""
    with patch("app.core.db.get_async_session_maker") as mock_session_maker:
        mock_session = MagicMock()
        mock_session_maker.return_value.__aenter__.return_value = mock_session
        mock_session.execute = AsyncMock()
        mock_session.execute.return_value.scalar_one_or_none = AsyncMock(
            return_value=None
        )

        response = client.get("/auth/session")

    assert response.status_code == 200
    data = response.json()
    assert data["authenticated"] is False
    assert "server_time" in data
