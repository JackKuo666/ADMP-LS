import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # OpenAI configuration - get from environment variables
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY")

    # Qianwen configuration - get from environment variables
    QIANWEN_BASE_URL: str = os.getenv("QIANWEN_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    QIANWEN_API_KEY: str = os.getenv("QIANWEN_API_KEY", "")

    # Search service URL - get from environment variables
    SEARCH_URL: str = os.getenv("SEARCH_URL", "http://0.0.0.0:9487")

    # Logging Configuration - get from environment variables
    LOG_DIR: str = os.getenv("LOG_DIR", ".log")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")  # DEBUG, INFO, WARNING, ERROR, CRITICAL
    LOG_MAX_SIZE: int = int(os.getenv("LOG_MAX_SIZE", "10485760"))  # 10MB
    LOG_BACKUP_COUNT: int = int(os.getenv("LOG_BACKUP_COUNT", "5"))
    LOG_ENABLE_CONSOLE: bool = os.getenv("LOG_ENABLE_CONSOLE", "true").lower() == "true"
    LOG_ENABLE_FILE: bool = os.getenv("LOG_ENABLE_FILE", "true").lower() == "true"

    # Debug mode - get from environment variables
    DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "true").lower() == "true"
    class Config:
        env_file = ".env"


settings = Settings()
