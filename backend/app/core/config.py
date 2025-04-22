from pydantic import BaseSettings, Field
from functools import lru_cache
import os
from typing import List, Optional


class Settings(BaseSettings):
    # --- General App Settings ---
    PROJECT_NAME: str = "Maritime Business Intelligence Platform"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: str = Field("development", description="Environment: development | production")

    # --- Server Settings ---
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    DEBUG: bool = True

    # --- Database ---
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "maritime_db"
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5432

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # --- Redis (para tracking y sesiones) ---
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_MAX_CONNECTIONS: int = int(os.getenv("REDIS_MAX_CONNECTIONS", "10"))

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/0"

    # --- JWT Auth ---
    JWT_SECRET_KEY: str = Field(..., description="Secret key for JWT tokens")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 1 day

    # --- DeepSeek AI ---
    DEEPSEEK_API_URL: str = "https://api.deepseek.com/infer"
    DEEPSEEK_API_KEY: str = Field(default="", description="DeepSeek API Key")

    # --- Phi-3 local path ---
    PHI3_MODEL_PATH: str = "./models/phi3"
    
    # --- AI Engine Configuration ---
    AI_ENGINE: str = os.getenv("AI_ENGINE", "phi3")  # Options: phi3, deepseek

    # --- CORS (dejar abierto en desarrollo) ---
    CORS_ORIGINS: List[str] = ["*"]
    
    # --- Logging ---
    LOG_DIR: str = os.getenv("LOG_DIR", "logs")
    API_LOG_LEVEL: str = os.getenv("API_LOG_LEVEL", "INFO")
    AUTH_LOG_LEVEL: str = os.getenv("AUTH_LOG_LEVEL", "INFO")
    DB_LOG_LEVEL: str = os.getenv("DB_LOG_LEVEL", "INFO")
    AI_LOG_LEVEL: str = os.getenv("AI_LOG_LEVEL", "INFO")
    
    # --- File Storage ---
    FILE_STORAGE_PATH: str = os.getenv("FILE_STORAGE_PATH", "storage")

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings():
    return Settings()


settings = get_settings()