"""Start-up configuration from the environment.

Only what is needed to *start* lives here (ADR 0014, ADR 0030). Everything the user
operates is a setting in the database and edited in the UI.
"""

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic import Field, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class ConfigError(RuntimeError):
    """Raised when the start-up configuration is unusable. Stops the start loudly."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    database_url: str = Field(default="", validate_default=False)
    # Or the parts, as the Unraid template asks for them (Vanixxx, 2026-10-12): host, port,
    # database, user, password in their own fields. DATABASE_URL wins when both are set.
    db_host: str | None = None
    db_port: int = 5432
    db_name: str = "owncryptofolio"
    db_user: str | None = None
    db_password: str | None = None
    app_env: str = "production"
    data_dir: Path = BACKEND_DIR / ".data"
    backup_dir: Path | None = None  # default: <data_dir>/backups
    db_wait_seconds: float = 60.0
    background_workers: bool = True  # job worker and backup schedule; off in tests
    frontend_dist: Path = BACKEND_DIR.parent / "frontend" / "dist"

    # Optional key overrides; generated on first start when absent (ADR 0030).
    credentials_key: str | None = None
    session_key: str | None = None
    backup_key: str | None = None

    @model_validator(mode="after")
    def _database(self) -> "Settings":
        if not self.database_url and self.db_host and self.db_user:
            auth = quote(self.db_user, safe="") + (
                ":" + quote(self.db_password, safe="") if self.db_password else ""
            )
            self.database_url = (
                f"postgresql+psycopg://{auth}@{self.db_host}:{self.db_port}/{self.db_name}"
            )
        if not self.database_url:
            raise ValueError("database_url")
        return self


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()
    except ValidationError as exc:
        missing = ", ".join(
            str(e["loc"][0]).upper() if e["loc"] else "DATABASE_URL (or DB_HOST, DB_USER, …)"
            for e in exc.errors()
        )
        raise ConfigError(f"Invalid or missing configuration: {missing}") from exc
