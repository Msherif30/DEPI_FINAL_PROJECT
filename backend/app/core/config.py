"""Central configuration, loaded from environment variables only."""
from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR / ".env"), str(BASE_DIR / "backend" / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "RestoMate AI"
    environment: str = "development"
    debug: bool = True

    db_host: str = "localhost"
    db_port: int = 3306
    db_user: str = "root"
    db_password: str = ""
    db_name: str = "bremer"
    database_url: str | None = None

    secret_key: str = ""
    access_token_expire_minutes: int = 480
    kiosk_session_minutes: int = 45
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173"

    # Optional LLM provider (OpenAI-compatible). Without a key the kiosk uses
    # its deterministic, fully functional local language engine.
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"

    upload_dir: str = str(BASE_DIR / "backend" / "uploads")
    ml_artifact_dir: str = str(BASE_DIR / "backend" / "ml_artifacts")
    log_level: str = "INFO"
    rate_limit_login_per_minute: int = 10

    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        from urllib.parse import quote_plus

        return (
            f"mysql+pymysql://{quote_plus(self.db_user)}:{quote_plus(self.db_password)}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}?charset=utf8mb4"
        )

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def effective_secret(self) -> str:
        if self.secret_key and not self.secret_key.startswith("change_me"):
            return self.secret_key
        # Deterministic local fallback so restarts in development do not
        # silently invalidate every session. Production must set SECRET_KEY.
        return "dev-only-" + hashlib.sha256(
            f"{self.db_host}:{self.db_name}:{self.db_user}".encode()
        ).hexdigest()


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)
    Path(settings.ml_artifact_dir).mkdir(parents=True, exist_ok=True)
    return settings


settings = get_settings()
