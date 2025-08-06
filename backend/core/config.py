"""
配置管理模块
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """应用配置"""
    
    # 基础配置
    APP_NAME: str = "SocialWise"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # 数据库配置
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "socialwise"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "password"
    
    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # Milvus配置
    MILVUS_HOST: str = "localhost"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION_NAME: str = "socialwise_vectors"
    
    # 通义千问配置
    DASHSCOPE_API_KEY: Optional[str] = None
    QWEN_MODEL: str = "qwen-turbo-latest"
    QWEN_EMBEDDING_MODEL: str = "text-embedding-v1"
    
    # 科大讯飞配置
    IFLYTEK_APP_ID: Optional[str] = None
    IFLYTEK_API_KEY: Optional[str] = None
    IFLYTEK_API_SECRET: Optional[str] = None
    
    # 语音配置
    ASR_LANGUAGE: str = "zh_cn"
    TTS_VOICE: str = "xiaoyan"
    TTS_SPEED: float = 1.0
    AUDIO_SAMPLE_RATE: int = 16000
    
    # 文件存储配置
    UPLOAD_DIR: str = "data/uploads"
    DOCUMENT_DIR: str = "data/documents"
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # Redis配置（会话管理）
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    SESSION_EXPIRE: int = 3600  # 1小时
    
    # 监控配置
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/socialwise.log"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# 创建全局配置实例
settings = Settings()

# 确保必要的目录存在
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.DOCUMENT_DIR, exist_ok=True)
os.makedirs("logs", exist_ok=True)