from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "EFI API"
    API_V1_STR: str = "/efi/v1"

    class Config:
        env_file = ".env"

settings = Settings()