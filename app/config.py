from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    keitaro_url: str = "https://tlgk.host"
    keitaro_api_key: str = ""
    campaign_prefix: str = "test_"
    database_url: str = "sqlite:///./keitaro_wrapper.db"
    google_url: str = "https://google.com"
    keitaro_timezone: str = "Europe/Moscow"


@lru_cache
def get_settings() -> Settings:
    return Settings()
