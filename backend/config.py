"""FieldIQ application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    chroma_persist_dir: str = "./data/chroma"
    raw_data_dir: str = "./data/raw"
    sqlite_db_path: str = "./data/app.db"

    backend_port: int = 8000
    frontend_url: str = "http://localhost:5173"


settings = Settings()
