import json
import pathlib

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


def _prefix_config(prefix: str) -> dict:
    credentials_path = CONFIG_DIR / "credentials.json"
    with credentials_path.open() as f:
        credentials = json.load(f)
    for creds in credentials:
        if creds["prefix"] == prefix:
            return creds
    raise RuntimeError(f"Did not find credentials for prefix {prefix}")


def get_handle_base_url(prefix: str) -> str:
    """Return the configured Handle API base URL for a trusted prefix.

    Only the endpoint is returned. Service credentials are never exposed.
    """
    base_url = _prefix_config(prefix)["base_url"]
    if base_url.endswith("/"):
        return base_url
    return f"{base_url}/"


def get_credentials(prefix: str) -> dict:
    result = {}
    creds = _prefix_config(prefix)
    result["base_url"] = get_handle_base_url(prefix)
    result["auth"] = BasicAuth(creds["username"], creds["password"])
    return result
