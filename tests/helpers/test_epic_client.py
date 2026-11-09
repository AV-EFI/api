from unittest.mock import MagicMock, patch

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
    with (
        patch("app.helpers.epic_client.get_credentials") as get_credentials,
        patch(
            "app.helpers.epic_client.get_handle_base_url"
        ) as get_handle_base_url,
    ):
        client = create_user_client(
            profile={},
            prefix="21.11155",
            username="SDK",
            password="client-password",
            base_url="https://handles.example/",
        )

    get_credentials.assert_not_called()
    get_handle_base_url.assert_not_called()
    assert client.base_url == "https://handles.example/"
    assert (
        client.auth._auth_header
        == BasicAuth("SDK", "client-password")._auth_header
    )
    client.close()


def test_explicit_epic_client_credentials_do_not_read_configuration():
    explicit_auth = BasicAuth("request-user", "request-password")
    with (
        patch("app.helpers.epic_client.get_credentials") as get_credentials,
        patch(
            "app.helpers.epic_client.get_handle_base_url"
        ) as get_handle_base_url,
    ):
        client = EpicClient(
            profile={},
            prefix="21.11155",
            base_url="https://handles.example/",
            auth=explicit_auth,
        )

    get_credentials.assert_not_called()
    get_handle_base_url.assert_not_called()
    assert client.base_url == "https://handles.example/"
    assert client.auth == explicit_auth
    client.close()


def test_explicit_base_url_keeps_explicit_connection_details():
    configured = {
        "base_url": "https://configured.example/",
        "auth": BasicAuth("service-user", "service-password"),
    }
    with patch(
        "app.helpers.epic_client.get_credentials", return_value=configured
    ) as get_credentials:
        client = EpicClient(
            profile={},
            prefix="21.11155",
            base_url="https://handles.example/",
        )

    get_credentials.assert_called_once_with("21.11155")
    assert client.base_url == "https://handles.example/"
    assert client.auth == configured["auth"]
    client.close()


def test_explicit_auth_without_base_url_uses_configured_endpoint():
    with (
        patch(
            "app.helpers.epic_client.get_handle_base_url",
            return_value="https://handles.example/",
        ) as get_handle_base_url,
        patch("app.helpers.epic_client.get_credentials") as get_credentials,
    ):
        client = EpicClient(
            profile={},
            prefix="21.11155",
            auth=BasicAuth("request-user", "request-password"),
        )

    get_handle_base_url.assert_called_once_with("21.11155")
    get_credentials.assert_not_called()
    assert client.base_url == "https://handles.example/"
    client.close()


def test_create_uses_explicit_planned_pid():
    client = create_user_client(
        profile={},
        prefix="21.11155",
        username="SDK",
        password="client-password",
        base_url="https://handles.example/",
    )
    record = MagicMock()

    with patch.object(client, "_put") as put:
        client.create(record, pid="21.11155/PLANNED")

    put.assert_called_once_with("21.11155/PLANNED", record, preexisting=False)
    client.close()


def test_create_generates_pid_when_none_is_supplied():
    client = create_user_client(
        profile={},
        prefix="21.11155",
        username="SDK",
        password="client-password",
        base_url="https://handles.example/",
        suffix="SUFFIX",
    )
    record = MagicMock()

    with patch.object(client, "_put") as put:
        client.create(record)

    pid = put.call_args.args[0]
    assert pid.startswith("21.11155/")
    assert pid.endswith("-SUFFIX")
    put.assert_called_once_with(pid, record, preexisting=False)
    client.close()
