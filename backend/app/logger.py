"""
日志配置
"""

import logging
import logging.handlers
import os
from backend.app.config import settings

def setup_logger():
    """设置日志配置"""
    # 确保日志目录存在
    log_dir = os.path.dirname(settings.LOG_FILE)
    os.makedirs(log_dir, exist_ok=True)
    
    # 创建根日志器
    logger = logging.getLogger("socialwise")
    logger.setLevel(getattr(logging, settings.LOG_LEVEL))
    
    # 避免重复添加处理器
    if logger.handlers:
        return logger
    
    # 创建格式化器
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # 文件处理器（带轮转）
    file_handler = logging.handlers.RotatingFileHandler(
        settings.LOG_FILE,
        maxBytes=settings.LOG_MAX_SIZE,
        backupCount=settings.LOG_BACKUP_COUNT,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    return logger

def get_logger(name: str = None):
    """获取日志器"""
    if name:
        return logging.getLogger(f"socialwise.{name}")
    return logging.getLogger("socialwise")

# 初始化日志
setup_logger()