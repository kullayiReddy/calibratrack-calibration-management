from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./calibratrack.db"
    secret_key: str = "development-only-change-me"
    access_token_minutes: int = 60
    upload_dir: str = "./data/uploads"
    max_upload_bytes: int = 10_485_760
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"


settings = Settings()
