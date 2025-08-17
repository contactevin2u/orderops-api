from pydantic_settings import BaseSettings
from pydantic import Field
from typing import List, Optional
import os

class Settings(BaseSettings):
    openai_api_key: str = Field(default="", alias="OPENAI_API_KEY")
    database_url: str = Field(default="", alias="DATABASE_URL")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    timezone_offset: str = Field(default="+08:00", alias="TIMEZONE_OFFSET")

    class Config:
        env_file = ".env"
        case_sensitive = False

def get_settings() -> "Settings":
    return Settings()
