"""Platform configuration and settings."""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "Burghscape Home Cloud"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    
    DATABASE_URL: str = "sqlite+aiosqlite:///./burghscape.db"
    REDIS_URL: str = "redis://:burghscape123@redis:6379/0"
    SECRET_KEY: str = "burghscape123"
    
    CLOUDFLARE_API_TOKEN: str = ""
    CLOUDFLARE_ZONE_ID: str = ""
    CLOUDFLARE_DOMAIN: str = "mybeacon.co.za"

    # R2 Backup Storage
    R2_ACCOUNT_ID: str = "606fea1660d6b2c997efcf6a26f5d79d"
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET: str = "burghscape-backups"
    R2_ENDPOINT: str = "https://606fea1660d6b2c997efcf6a26f5d79d.r2.cloudflarestorage.com"

    LOG_LEVEL: str = "INFO"
    BACKUP_RETENTION_DAYS: int = 30
    BACKUP_SFTP_HOST: str = ""
    BACKUP_SFTP_USER: str = ""
    BACKUP_SFTP_PATH: str = ""
    MONITOR_INTERVAL: int = 60


@lru_cache()
def get_settings() -> Settings:
    return Settings()

