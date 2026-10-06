from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="INBOXOS_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://inboxos:inboxos@localhost:5432/inboxos"
    intelligence_provider: Literal["fixture"] = "fixture"
    log_level: str = "INFO"

    @model_validator(mode="after")
    def fixture_provider_is_not_allowed_in_production(self) -> "Settings":
        if self.environment == "production" and self.intelligence_provider == "fixture":
            raise ValueError("The fixture intelligence provider cannot be used in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()

