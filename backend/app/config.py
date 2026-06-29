"""Platform configuration and settings."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Burghscape Home Cloud"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    DATABASE_URL: str = "postgresql+asyncpg://burghscape:burghscape123@postgres:5432/burghscape"
    REDIS_URL: str = "redis://:burghscape123@redis:6379/0"
    SECRET_KEY: str = "burghscape123"
    
    CLOUDFLARE_API_TOKEN: str = ""
    CLOUDFLARE_ZONE_ID: str = ""
    CLOUDFLARE_DOMAIN: str = "mybeacon.co.za"
    
    ONEDRIVE_CLIENT_ID: str = ""
    ONEDRIVE_CLIENT_SECRET: str = ""
    ONEDRIVE_TENANT_ID: str = "common"
    
    LOG_LEVEL: str = "INFO"
    BACKUP_RETENTION_DAYS: int = 30
    MONITOR_INTERVAL: int = 60


@lru_cache()
def get_settings() -> Settings:
    return Settings()
