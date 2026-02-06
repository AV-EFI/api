from fastapi_csrf_protect import CsrfProtect
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "EFI API"
    # To be changed in local env
    SESSION_SECRET: str = "secret_for_session_cookies"

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

    PID_SERVICE_URL: str = "http://pid.av-efi.net:8081/handles/21.T11998"
    PID_SERVICE_ADDRESS: str = "http://pid.av-efi.net:8081"
    PID_USERNAME: str = ""
    PID_PASSWORD: str = ""

    model_config = ConfigDict(
        env_file = ".api_config.env",
    )


settings = Settings()


class CsrfSettings(BaseSettings):
    secret_key: str = settings.SESSION_SECRET
    cookie_samesite: str = "none"
    cookie_secure: bool = True
    token_location: str = "body"
    token_key: str = "csrf-token"


@CsrfProtect.load_config
def get_csrf_config():
    return CsrfSettings()
