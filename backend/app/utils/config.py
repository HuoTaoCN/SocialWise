"""
配置管理
"""

import os
from typing import Optional
from pydantic import BaseSettings

class Settings(BaseSettings):
    """应用配置"""
    
    # 应用基础配置
    APP_NAME: str = "社保智答/SocialWise"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # 数据库配置
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "socialwise"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_DB: str = "socialwise"
    
    # Redis配置
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    
    # Milvus配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    
    # 科大讯飞配置
    IFLYTEK_APP_ID: str = ""
    IFLYTEK_API_KEY: str = ""
    IFLYTEK_API_SECRET: str = ""
    
    # 通义千问配置
    DASHSCOPE_API_KEY: str = ""
    
    # 文件存储配置
    UPLOAD_PATH: str = "/data/uploads"
    DOCUMENTS_PATH: str = "/data/documents"
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "/var/log/socialwise/app.log"
    
    # 安全配置
    SECRET_KEY: str = "your-secret-key-here"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# 创建全局配置实例
settings = Settings()