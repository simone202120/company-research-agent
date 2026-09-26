"""Application settings loaded from environment variables (and `.env` in local development)."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ConfigurationError(Exception):
    """A required setting is missing or invalid."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openrouter_api_key: SecretStr = SecretStr("")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "google/gemini-3.8-flash"
    llm_timeout_seconds: float = 60
    # USD per million tokens, used only to show an estimated cost per research.
    llm_input_price_per_mtok: float = 0.30
    llm_output_price_per_mtok: float = 2.50

    langfuse_public_key: str = ""
    langfuse_secret_key: SecretStr = SecretStr("")
    langfuse_host: str = "https://cloud.langfuse.com"

    tavily_api_key: SecretStr = SecretStr("")
    search_max_results: int = 5
    checkpoint_db: str = "data/checkpoints.sqlite"
    max_revisions: int = 1

    api_url: str = "http://localhost:8000"

    @property
    def tracing_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key.get_secret_value())


@lru_cache
def get_settings() -> Settings:
    return Settings()
