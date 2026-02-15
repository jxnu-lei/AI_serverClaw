from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """应用配置"""
    # 基本配置
    PROJECT_NAME: str = "AI Terminal"
    VERSION: str = "1.0.0"
    DEBUG: bool = True

    # 数据库配置
    DATABASE_URL: str = "sqlite+aiosqlite:///./ai_terminal.db"
    # 生产环境使用 PostgreSQL
    # DATABASE_URL: str = "postgresql+asyncpg://user:pass@localhost:5432/ai_terminal"

    # JWT 配置
    SECRET_KEY: str = "your-secret-key-here"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # 加密配置
    ENCRYPTION_KEY: str = "your-encryption-key-here"

    # CORS 配置
    CORS_ORIGINS: List[str] = ["*"]

    # LLM 配置
    DEFAULT_LLM_PROVIDER: str = "deepseek"
    DEFAULT_LLM_API_URL: str = "https://api.deepseek.com/v1"
    DEFAULT_LLM_MODEL: str = "deepseek-chat"
    DEFAULT_LLM_API_KEY: str = ""  # 系统默认API Key，用于所有用户

    # 默认管理员配置
    DEFAULT_ADMIN_USERNAME: str = "admin"
    DEFAULT_ADMIN_PASSWORD: str = "admin!123"
    DEFAULT_ADMIN_EMAIL: str = "admin@example.com"

    # 额外的环境变量，用于兼容 Docker 部署
    API_HOST: str = "http://localhost:8000"
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()
