import json

from httpx2 import BasicAuth
import pytest

from app.core import config as config_module
from app.core.config import (
    HandleConfigIncomplete,
    HandleConfigUnreadable,
    HandlePrefixNotConfigured,
    get_credentials,
    get_handle_base_url,
    require_handle_service_credentials,
)


@pytest.fixture
def config_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config_module, "CONFIG_DIR", tmp_path)
    return tmp_path


def _write_credentials(config_dir, entries):
    (config_dir / "credentials.json").write_text(json.dumps(entries))


def test_get_handle_base_url_requires_only_base_url(config_dir):
    _write_credentials(
        config_dir,
        [{"prefix": "21.11155", "base_url": "https://handles.example"}],
    )

    assert get_handle_base_url("21.11155") == "https://handles.example/"
    with pytest.raises(HandleConfigIncomplete) as exc_info:
        require_handle_service_credentials("21.11155")

    assert exc_info.value.prefix == "21.11155"
    assert exc_info.value.missing == ("username", "password")


def test_complete_entry_provides_credentials(config_dir):
    _write_credentials(
        config_dir,
        [
            {
                "prefix": "21.11155",
                "base_url": "https://handles.example/",
                "username": "service-user",
                "password": "service-password",
            }
        ],
    )

    require_handle_service_credentials("21.11155")
    credentials = get_credentials("21.11155")

    assert credentials["base_url"] == "https://handles.example/"
    assert (
        credentials["auth"]._auth_header
        == BasicAuth("service-user", "service-password")._auth_header
    )


def test_missing_prefix_raises_handle_prefix_not_configured(config_dir):
    _write_credentials(
        config_dir,
        [{"prefix": "21.11155", "base_url": "https://handles.example/"}],
    )

    with pytest.raises(HandlePrefixNotConfigured) as exc_info:
        get_handle_base_url("other")

    assert exc_info.value.prefix == "other"


def test_missing_file_raises_handle_config_unreadable(config_dir):
    with pytest.raises(HandleConfigUnreadable) as exc_info:
        get_handle_base_url("21.11155")

    assert exc_info.value.path == config_dir / "credentials.json"
    assert exc_info.value.reason == "file not found"


def test_malformed_json_raises_handle_config_unreadable(config_dir):
    (config_dir / "credentials.json").write_text("{")

    with pytest.raises(HandleConfigUnreadable) as exc_info:
        get_handle_base_url("21.11155")

    assert "invalid JSON" in str(exc_info.value)


def test_wrong_root_shape_raises_handle_config_unreadable(config_dir):
    _write_credentials(config_dir, {"prefix": "21.11155"})

    with pytest.raises(HandleConfigUnreadable) as exc_info:
        get_handle_base_url("21.11155")

    assert "expected a list" in str(exc_info.value)


def test_non_object_entry_raises_handle_config_unreadable(config_dir):
    _write_credentials(config_dir, ["not-an-object"])

    with pytest.raises(HandleConfigUnreadable) as exc_info:
        get_handle_base_url("21.11155")

    assert "not an object" in str(exc_info.value)


def test_incomplete_entry_reports_only_missing_field_names(config_dir):
    _write_credentials(
        config_dir,
        [
            {
                "prefix": "21.11155",
                "base_url": "https://handles.example/",
                "password": "do-not-log-this",
            }
        ],
    )

    with pytest.raises(HandleConfigIncomplete) as exc_info:
        require_handle_service_credentials("21.11155")

    assert exc_info.value.missing == ("username",)
    assert "username" in str(exc_info.value)
    assert "do-not-log-this" not in str(exc_info.value)
