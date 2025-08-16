from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
import os

# Load backend/.env regardless of CWD
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ENV_PATH = os.path.join(BASE_DIR, ".env")
load_dotenv(ENV_PATH)

class Settings(BaseSettings):
    DATABASE_URL: str
    REDIS_URL: str | None = None
    OPENAI_API_KEY: str | None = None
    CORS_ORIGIN: str = "*"
    SENTRY_DSN: str | None = None
    AWS_ACCESS_KEY_ID: str | None = None
    AWS_SECRET_ACCESS_KEY: str | None = None
    AWS_DEFAULT_REGION: str | None = None
    S3_BUCKET: str | None = None
    QUEUE_DISABLED: bool = True
    EMBED_MODEL: str = "text-embedding-3-small"
    EMBED_DIM: int = 1536

    # pydantic-settings v2 style config
    model_config = SettingsConfigDict(
        env_file=ENV_PATH,
        env_file_encoding="utf-8",
        case_sensitive=True
    )

settings = Settings()
