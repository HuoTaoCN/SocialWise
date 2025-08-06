"""
数据库模型和连接管理
"""

import asyncio
import logging
from typing import Optional
import asyncpg
from contextlib import asynccontextmanager

from ..utils.config import settings

logger = logging.getLogger(__name__)

# 数据库连接池
_connection_pool: Optional[asyncpg.Pool] = None

async def init_db():
    """初始化数据库连接池"""
    global _connection_pool
    
    try:
        _connection_pool = await asyncpg.create_pool(
            host=settings.POSTGRES_HOST,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            database=settings.POSTGRES_DB,
            min_size=5,
            max_size=20,
            command_timeout=60
        )
        
        logger.info("数据库连接池初始化成功")
        
        # 创建表结构
        await create_tables()
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
        raise

@asynccontextmanager
async def get_db_connection():
    """获取数据库连接"""
    if not _connection_pool:
        await init_db()
    
    async with _connection_pool.acquire() as connection:
        yield connection

async def create_tables():
    """创建数据库表结构"""
    try:
        async with get_db_connection() as conn:
            # 创建扩展
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            await conn.execute("CREATE EXTENSION IF NOT EXISTS zhparser;")
            
            # 文档表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS documents (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    file_path TEXT NOT NULL,
                    doc_type VARCHAR(50) NOT NULL,
                    total_chunks INTEGER DEFAULT 0,
                    success_chunks INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # FAQ表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS faq (
                    id SERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    category VARCHAR(100),
                    priority INTEGER DEFAULT 1,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 可信QA对表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS trusted_qa (
                    id SERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    source VARCHAR(255),
                    confidence DECIMAL(3,2) DEFAULT 0.80,
                    verified_by VARCHAR(100),
                    verified_at TIMESTAMP,
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 生成QA对表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS generated_qa (
                    id SERIAL PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    source VARCHAR(255),
                    confidence DECIMAL(3,2) DEFAULT 0.80,
                    is_verified BOOLEAN DEFAULT false,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 会话表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) UNIQUE NOT NULL,
                    user_id VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # 消息表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
                );
            """)
            
            # 用户反馈表
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS user_feedback (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(255) NOT NULL,
                    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
                );
            """)
            
            # 创建索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_faq_search ON faq USING gin(to_tsvector('chinese', question || ' ' || answer));")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_trusted_qa_search ON trusted_qa USING gin(to_tsvector('chinese', question || ' ' || answer));")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id);")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at);")
            
        logger.info("数据库表结构创建完成")
        
    except Exception as e:
        logger.error(f"创建数据库表失败: {str(e)}")
        raise

async def close_db():
    """关闭数据库连接池"""
    global _connection_pool
    if _connection_pool:
        await _connection_pool.close()
        _connection_pool = None
        logger.info("数据库连接池已关闭")