from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./calibratrack.db"
    secret_key: str = "development-only-change-me"
    access_token_minutes: int = 60
    upload_dir: str = "./data/uploads"
    max_upload_bytes: int = 10_485_760
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    @property
    def sqlalchemy_database_url(self) -> str:
        # Render provides postgres:// or postgresql://. The project installs
        # psycopg 3, so select its SQLAlchemy dialect explicitly.
        if self.database_url.startswith("postgres://"):
            return self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        if self.database_url.startswith("postgresql://"):
            return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self.database_url


settings = Settings()
