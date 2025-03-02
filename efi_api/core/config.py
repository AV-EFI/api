from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "EFI API"
    API_V1_STR: str = "/efi/v1"

    # Elasticsearch settings
    ES_HOST: str = "pid.av-efi.net"
    ES_PORT: int = 9200
    # ES_INDEX: str = "21.11155_test_nested"
    # ES_INDEX: str = "21.11155-dev-runtime"
    ES_INDEX: str = "21.11155-denormalised-work"
    ES_SCHEME: str = "http"
    
    # Auth settings
    SECRET_KEY: str = "some-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    PID_SERVICE_URL: str = "http://pid.av-efi.net:8081/handles/21.T11998"
    PID_SERVICE_ADDRESS: str = "http://pid.av-efi.net:8081"
    PID_USERNAME: str = "" #TODO: UPDATE USERNAME TO AUTHENTICATE AGAINST PID SYSTEM; CAN BE DONE IN .ENV FILE
    PID_PASSWORD: str = "" #TODO: UPDATE PASSWORD TO AUTHENTICATE AGAINST PID SYSTEM; CAN BE DONE IN .ENV FILE
    
    class Config:
        env_file = ".api_config.env"

settings = Settings()
