from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    printify_api_token: str = ""
    printify_shop_id: str = ""
    printify_api_base: str = "https://api.printify.com/v1"

    database_url: str = "sqlite:///./app.db"
    upload_dir: str = "./uploads"
    cors_origins: str = "http://localhost:5173"

    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
