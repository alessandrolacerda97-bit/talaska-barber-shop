import os
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(value: str) -> str:
    """Make a standard Neon URL usable by SQLAlchemy + psycopg 3.

    Neon displays `postgresql://...` by default while this application installs
    psycopg 3. SQLAlchemy needs the explicit `postgresql+psycopg://` dialect.
    """

    url = value.strip()
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./talaska.db"
    secret_key: str = "development-secret-change-me"
    admin_email: str = "admin@talaskabarbershop.com.br"
    admin_initial_password: str = "change-me"
    frontend_origins: str = "http://localhost:5173"
    environment: str = "development"
    cancellation_hours: int = 2
    appointment_interval_minutes: int = 30

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_neon_database_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def origins(self) -> list[str]:
        return [item.strip().rstrip("/") for item in self.frontend_origins.split(",") if item.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"production", "prod"} or bool(os.getenv("RENDER"))

    def validate_for_startup(self) -> None:
        """Fail closed when a Render/production service uses sample secrets."""

        if not self.is_production:
            return

        errors: list[str] = []
        if self.database_url.startswith("sqlite"):
            errors.append("DATABASE_URL precisa apontar para o PostgreSQL/Neon em produção")
        if self.secret_key in {"development-secret-change-me", "change-me", "replace-with-a-long-random-secret"} or len(self.secret_key) < 32:
            errors.append("SECRET_KEY precisa ser forte e ter pelo menos 32 caracteres")
        if self.admin_initial_password in {"change-me", "change-this-before-production", ""} or len(self.admin_initial_password) < 12:
            errors.append("ADMIN_INITIAL_PASSWORD precisa ser uma senha inicial forte")
        if not self.origins or any("localhost" in origin for origin in self.origins):
            errors.append("FRONTEND_ORIGINS precisa conter somente a URL pública do frontend")
        if errors:
            raise RuntimeError("Configuração insegura de produção: " + "; ".join(errors))


@lru_cache
def get_settings() -> Settings:
    return Settings()
