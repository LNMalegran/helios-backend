# backend/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class Settings(BaseSettings):
    secret_key: str = "default-dev-secret-key-CHANGE-IN-PRODUCTION-12345"
    database_url: str = "sqlite:///./game.db"
    osrm_url: str = "https://router.project-osrm.org"
    time_speed_modifier: float = 2.5
    
    model_config = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


settings = Settings()
