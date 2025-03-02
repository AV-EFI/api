from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "EFI API"
    SESSION_SECRET: str = "secret_for_session_cookies" # To be changed in local env

    # Elasticsearch settings
    ES_HOST: str = "pid.av-efi.net"
    ES_PORT: int = 9200
    # ES_INDEX: str = "21.11155_test_nested"
    # ES_INDEX: str = "21.11155-dev-runtime"
    ES_INDEX: str = "21.11155-denormalised-work"
    ES_SCHEME: str = "http"
    
    # Auth settings to be configured in local env
    AC_CLIENT_ID: str = ""
    AC_SECRET_KEY: str = ""
    AC_METADATA_URL: str = ""
    ALGORITHM: str = "HS256"

    PID_SERVICE_URL: str = "http://pid.av-efi.net:8081/handles/21.T11998"
    PID_SERVICE_ADDRESS: str = "http://pid.av-efi.net:8081"
    PID_USERNAME: str = "" #TODO: UPDATE USERNAME TO AUTHENTICATE AGAINST PID SYSTEM; CAN BE DONE IN .ENV FILE
    PID_PASSWORD: str = "" #TODO: UPDATE PASSWORD TO AUTHENTICATE AGAINST PID SYSTEM; CAN BE DONE IN .ENV FILE

    class Config:
        env_file = ".api_config.env"

settings = Settings()
