from unittest.mock import patch

from httpx2 import BasicAuth

from app.helpers.epic_client import (
    EpicClient,
    create_service_client,
    create_user_client,
)


def test_service_client_uses_credentials_for_prefix():
    configured = {
        "base_url": "https://handles.example/",
        "auth": BasicAuth("service-user", "service-password"),
    }
    with patch(
        "app.helpers.epic_client.get_credentials", return_value=configured
    ) as get_credentials:
        client = create_service_client(profile={}, prefix="21.11155")

    get_credentials.assert_called_once_with("21.11155")
    assert client.base_url == "https://handles.example/"
    assert client.auth == configured["auth"]
    client.close()


def test_user_client_uses_explicit_in_memory_credentials():
    configured = {
        "base_url": "https://configured.example/",
        "auth": BasicAuth("service-user", "service-password"),
    }
    with patch(
        "app.helpers.epic_client.get_credentials", return_value=configured
    ) as get_credentials:
        client = create_user_client(
            profile={},
            prefix="21.11155",
            username="SDK",
            password="client-password",
            base_url="https://handles.example/",
        )

    get_credentials.assert_called_once_with("21.11155")
    assert client.base_url == "https://handles.example/"
    assert (
        client.auth._auth_header
        == BasicAuth("SDK", "client-password")._auth_header
    )
    client.close()


def test_explicit_epic_client_credentials_override_configured_values():
    configured = {
        "base_url": "https://configured.example/",
        "auth": BasicAuth("service-user", "service-password"),
    }
    explicit_auth = BasicAuth("request-user", "request-password")
    with patch(
        "app.helpers.epic_client.get_credentials", return_value=configured
    ):
        client = EpicClient(
            profile={},
            prefix="21.11155",
            base_url="https://handles.example/",
            auth=explicit_auth,
        )

    assert client.base_url == "https://handles.example/"
    assert client.auth == explicit_auth
    client.close()
