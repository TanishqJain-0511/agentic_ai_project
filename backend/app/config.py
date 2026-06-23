from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

import os
class Settings(BaseSettings):
    load_dotenv()
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = os.getenv("DATABASE_URL")
    REDIS_URL: str = "redis://redis:6379/0"

    SECRET_KEY: str = "super-secret-key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "http://localhost:3000"

    OLLAMA_HOST: str = "http://localhost:11434"

settings = Settings()
