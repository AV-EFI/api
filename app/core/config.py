import json
import pathlib
from typing import Any

from fastapi_csrf_protect import CsrfProtect
from httpx2 import BasicAuth
from pydantic import ConfigDict
from pydantic_settings import BaseSettings

CONFIG_DIR = pathlib.Path("config")


class Settings(BaseSettings):
    APP_NAME: str = "EFI API"
    # To be changed in local env
    SESSION_SECRET: str = "secret_for_session_cookies"
    # CSRF protection secret (defaults to SESSION_SECRET)
    CSRF_SECRET: str = ""

    # Elasticsearch settings
    ES_HOST: str = "pid.av-efi.net"
    ES_PORT: int = 9200
    # ES_INDEX: str = "21.11155_test_nested"
    # ES_INDEX: str = "21.11155-dev-runtime"
    ES_INDEX: str = "21.11155-denormalised-work"
    ES_LOOKUP_INDEX: str = "21.11155-nested"
    ES_PRIMARY_INDEX: str = "21.11155"
    ES_SCHEME: str = "http"

    # Auth settings to be configured in local env
    AC_CLIENT_ID: str = ""
    AC_SECRET_KEY: str = ""
    AC_METADATA_URL: str = ""
    ALGORITHM: str = "HS256"

    # Database settings
    DATABASE_URL: str = ""

    # Session settings
    SESSION_COOKIE_MAX_AGE: int = 16 * 60 * 60  # 16 hours
    SESSION_CLEANUP_ENABLED: bool = True
    SESSION_CLEANUP_INTERVAL: int = 3600  # 1 hour

    # PID settings
    CONNECTION_TIMEOUT: int = 180
    PID_SERVICE_URL: str = "http://pid.av-efi.net:8081/handles/21.T11998"
    PID_SERVICE_ADDRESS: str = "http://pid.av-efi.net:8081"
    PID_USERNAME: str = ""
    PID_PASSWORD: str = ""

    # Submission settings
    SUBMISSION_MAX_BODY_BYTES: int = 10 * 1024 * 1024
    SUBMISSION_MAX_RECORDS: int = 2000
    SUBMISSION_MAX_QUEUED_JOBS_PER_PROVIDER: int = 100
    SUBMISSION_MAX_QUEUED_BYTES_PER_PROVIDER: int = 500 * 1024 * 1024
    SUBMISSION_JOURNAL_PAGE_SIZE: int = 500

    # Submission worker settings
    SUBMISSION_WORKER_MAX_ATTEMPTS: int = 3
    SUBMISSION_WORKER_RETRY_BASE_SECONDS: int = 10
    SUBMISSION_WORKER_RETRY_MAX_SECONDS: int = 10 * 60
    SUBMISSION_WORKER_LEASE_SECONDS: int = 5 * 60
    SUBMISSION_WORKER_POLL_SECONDS: int = 2

    model_config = ConfigDict(
        env_file=CONFIG_DIR / "config.ini",
    )


settings = Settings()


class CsrfSettings(BaseSettings):
    secret_key: str = settings.CSRF_SECRET or settings.SESSION_SECRET
    cookie_samesite: str = "lax"
    cookie_secure: bool = True
    token_location: str = "header"
    token_key: str = "X-CSRF-Token"
    max_age: int = 3600


@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()


REQUIRED_HANDLE_FIELDS = ("base_url", "username", "password")


class HandleConfigError(RuntimeError):
    """Base class for missing or invalid server-side Handle configuration."""


class HandlePrefixNotConfigured(HandleConfigError):
    """No server-side Handle configuration exists for a prefix."""

    def __init__(self, prefix: str):
        self.prefix = prefix
        super().__init__(
            f"No server-side Handle configuration for prefix {prefix}"
        )


class HandleConfigIncomplete(HandleConfigError):
    """A Handle configuration entry is missing required fields."""

    def __init__(self, prefix: str, missing: tuple[str, ...]):
        self.prefix = prefix
        self.missing = missing
        super().__init__(
            f"Server-side Handle configuration for prefix {prefix} is "
            f"incomplete; missing: {', '.join(missing)}"
        )


class HandleConfigUnreadable(HandleConfigError):
    """The Handle configuration file cannot be read or parsed."""

    def __init__(self, path: pathlib.Path, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Cannot read Handle configuration {path}: {reason}")


def _load_prefix_config(prefix: str) -> dict[str, Any]:
    credentials_path = CONFIG_DIR / "credentials.json"
    try:
        with credentials_path.open() as f:
            credentials = json.load(f)
    except FileNotFoundError as exc:
        raise HandleConfigUnreadable(
            credentials_path, "file not found"
        ) from exc
    except OSError as exc:
        raise HandleConfigUnreadable(
            credentials_path, exc.strerror or str(exc)
        ) from exc
    except UnicodeDecodeError as exc:
        raise HandleConfigUnreadable(
            credentials_path, "file is not valid UTF-8"
        ) from exc
    except json.JSONDecodeError as exc:
        raise HandleConfigUnreadable(
            credentials_path,
            f"invalid JSON at line {exc.lineno} column {exc.colno}",
        ) from exc

    if not isinstance(credentials, list):
        raise HandleConfigUnreadable(
            credentials_path, "expected a list of prefix entries"
        )
    for index, creds in enumerate(credentials):
        if not isinstance(creds, dict):
            raise HandleConfigUnreadable(
                credentials_path, f"entry {index} is not an object"
            )
        if creds.get("prefix") == prefix:
            return creds
    raise HandlePrefixNotConfigured(prefix)


def _require_fields(
    prefix: str, creds: dict[str, Any], fields: tuple[str, ...]
) -> None:
    missing = tuple(
        field
        for field in fields
        if not isinstance(creds.get(field), str) or not creds[field]
    )
    if missing:
        raise HandleConfigIncomplete(prefix, missing)


def _normalise_base_url(base_url: str) -> str:
    if base_url.endswith("/"):
        return base_url
    return f"{base_url}/"


def get_handle_base_url(prefix: str) -> str:
    """Return the configured Handle API base URL for a trusted prefix.

    Only the endpoint is required. Service credentials are not validated
    here, so status reads do not depend on worker credentials.
    """
    creds = _load_prefix_config(prefix)
    _require_fields(prefix, creds, ("base_url",))
    return _normalise_base_url(creds["base_url"])


def require_handle_service_credentials(prefix: str) -> None:
    """Require complete server-side Handle credentials for ``prefix``.

    A submission may only be accepted if the worker can later process it
    with configured server-side credentials.
    """
    creds = _load_prefix_config(prefix)
    _require_fields(prefix, creds, REQUIRED_HANDLE_FIELDS)


def get_credentials(prefix: str) -> dict:
    creds = _load_prefix_config(prefix)
    _require_fields(prefix, creds, REQUIRED_HANDLE_FIELDS)
    result = {}
    result["base_url"] = _normalise_base_url(creds["base_url"])
    result["auth"] = BasicAuth(creds["username"], creds["password"])
    return result
