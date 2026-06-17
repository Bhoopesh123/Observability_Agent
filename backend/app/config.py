from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    frontend_port: int = Field(default=3005, alias="FRONTEND_PORT")

    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4.1-mini", alias="OPENAI_MODEL")

    grafana_url: str | None = Field(default=None, alias="GRAFANA_URL")
    grafana_api_key: str | None = Field(default=None, alias="GRAFANA_API_KEY")
    grafana_org_id: int | None = Field(default=1, alias="GRAFANA_ORG_ID")
    default_datasource_uid: str | None = Field(default=None, alias="DEFAULT_DATASOURCE_UID")
    default_loki_datasource_uid: str | None = Field(default=None, alias="DEFAULT_LOKI_DATASOURCE_UID")

    default_lookback_minutes: int = Field(default=30, alias="DEFAULT_LOOKBACK_MINUTES")
    request_timeout_seconds: float = Field(default=15, alias="REQUEST_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def cors_origins(self) -> list[str]:
        return [
            f"http://localhost:{self.frontend_port}",
            f"http://127.0.0.1:{self.frontend_port}",
        ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
