from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "EFI API"
    API_V1_STR: str = "/efi/v1"

    # Elasticsearch settings
    ES_HOST: str = "141.5.105.237"
    ES_PORT: int = 9200
    ES_INDEX: str = "21.11155_test_nested"
    ES_SCHEME: str = "http"
    class Config:
        env_file = ".env"

settings = Settings()