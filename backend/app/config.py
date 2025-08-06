"""
应用配置管理
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """应用设置"""
    
    # 基本应用信息
    APP_NAME: str = "SocialWise"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # 服务器配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # 数据库配置 - PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "socialwise"
    POSTGRES_PASSWORD: str = "socialwise123"
    POSTGRES_DB: str = "socialwise"
    
    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_DB: int = 0
    
    # Milvus配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    
    # API密钥配置
    IFLYTEK_APP_ID: str = ""
    IFLYTEK_API_SECRET: str = ""
    IFLYTEK_API_KEY: str = ""
    
    DASHSCOPE_API_KEY: str = ""  # 通义千问API密钥
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/socialwise.log"
    LOG_MAX_SIZE: int = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT: int = 5
    
    # 文件存储配置
    UPLOAD_DIR: str = "uploads"
    DOCUMENTS_DIR: str = "documents"
    AUDIO_DIR: str = "audio"
    
    # 安全配置
    SECRET_KEY: str = "socialwise-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS配置
    ALLOWED_ORIGINS: list = ["*"]
    
    # 业务配置
    MAX_AUDIO_SIZE: int = 10 * 1024 * 1024  # 10MB
    MAX_DOCUMENT_SIZE: int = 50 * 1024 * 1024  # 50MB
    SESSION_EXPIRE_HOURS: int = 24
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# 创建全局设置实例
settings = Settings()

# 确保必要的目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.DOCUMENTS_DIR, exist_ok=True)
os.makedirs(settings.AUDIO_DIR, exist_ok=True)
os.makedirs(os.path.dirname(settings.LOG_FILE), exist_ok=True)