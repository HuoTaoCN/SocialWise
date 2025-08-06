"""
数据库连接和表结构管理
"""

import asyncio
import logging
from typing import Optional
import asyncpg
from datetime import datetime

from .config import settings

logger = logging.getLogger(__name__)

class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self):
        self.pool = None
    
    async def initialize(self):
        """初始化数据库连接池"""
        try:
            self.pool = await asyncpg.create_pool(
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                database=settings.POSTGRES_DB,
                min_size=5,
                max_size=20
            )
            
            # 创建表结构
            await self.create_tables()
            
            logger.info("数据库连接池初始化成功")
            
        except Exception as e:
            logger.error(f"数据库连接池初始化失败: {str(e)}")
            raise
    
    async def create_tables(self):
        """创建数据库表结构"""
        try:
            async with self.pool.acquire() as conn:
                # 创建文档表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS documents (
                        id VARCHAR(100) PRIMARY KEY,
                        filename VARCHAR(255) NOT NULL,
                        file_path TEXT NOT NULL,
                        document_type VARCHAR(50) DEFAULT 'raw',
                        content TEXT,
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建FAQ表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS faq (
                        id SERIAL PRIMARY KEY,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        category VARCHAR(100),
                        tags JSONB DEFAULT '[]',
                        is_active BOOLEAN DEFAULT true,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建可信问答表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS trusted_qa (
                        id SERIAL PRIMARY KEY,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        source VARCHAR(255),
                        confidence_score FLOAT DEFAULT 0.0,
                        tags JSONB DEFAULT '[]',
                        is_verified BOOLEAN DEFAULT false,
                        verifier VARCHAR(100),
                        verified_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建生成问答表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS generated_qa (
                        id SERIAL PRIMARY KEY,
                        question TEXT NOT NULL,
                        answer TEXT NOT NULL,
                        source VARCHAR(255),
                        confidence_score FLOAT DEFAULT 0.0,
                        metadata JSONB DEFAULT '{}',
                        is_verified BOOLEAN,
                        verifier VARCHAR(100),
                        verification_notes TEXT,
                        verified_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # 创建聊天会话表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS chat_sessions (
                        id VARCHAR(100) PRIMARY KEY,
                        user_id VARCHAR(100),
                        session_data JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP
                    )
                """)
                
                # 创建聊天消息表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS chat_messages (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(100) NOT NULL,
                        role VARCHAR(20) NOT NULL,
                        content TEXT NOT NULL,
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE
                    )
                """)
                
                # 创建用户反馈表
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_feedback (
                        id SERIAL PRIMARY KEY,
                        session_id VARCHAR(100),
                        message_id INTEGER,
                        rating INTEGER CHECK (rating >= 1 AND rating <= 5),
                        comment TEXT,
                        metadata JSONB DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE SET NULL,
                        FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE SET NULL
                    )
                """)
                
                # 创建索引
                await self._create_indexes(conn)
                
                logger.info("数据库表结构创建完成")
                
        except Exception as e:
            logger.error(f"创建数据库表失败: {str(e)}")
            raise
    
    async def _create_indexes(self, conn):
        """创建数据库索引"""
        try:
            # 文档表索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(document_type)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_created ON documents(created_at)")
            
            # FAQ表索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_faq_category ON faq(category)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_faq_active ON faq(is_active)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_faq_question_text ON faq USING gin(to_tsvector('chinese', question))")
            
            # 可信问答表索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_trusted_qa_verified ON trusted_qa(is_verified)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_trusted_qa_confidence ON trusted_qa(confidence_score)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_trusted_qa_question_text ON trusted_qa USING gin(to_tsvector('chinese', question))")
            
            # 生成问答表索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_generated_qa_verified ON generated_qa(is_verified)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_generated_qa_confidence ON generated_qa(confidence_score)")
            
            # 聊天会话表索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_sessions_expires ON chat_sessions(expires_at)")
            
            # 聊天消息表索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_session ON chat_messages(session_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_chat_messages_created ON chat_messages(created_at)")
            
            # 用户反馈表索引
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_session ON user_feedback(session_id)")
            await conn.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_rating ON user_feedback(rating)")
            
            logger.info("数据库索引创建完成")
            
        except Exception as e:
            logger.error(f"创建数据库索引失败: {str(e)}")
    
    async def get_connection(self):
        """获取数据库连接"""
        if not self.pool:
            await self.initialize()
        return self.pool.acquire()
    
    async def close(self):
        """关闭数据库连接池"""
        if self.pool:
            await self.pool.close()
            logger.info("数据库连接池已关闭")

# 全局数据库管理器实例
db_manager = DatabaseManager()

async def get_db_connection():
    """获取数据库连接的便捷函数"""
    return await db_manager.get_connection()

async def init_database():
    """初始化数据库的便捷函数"""
    await db_manager.initialize()

async def close_database():
    """关闭数据库的便捷函数"""
    await db_manager.close()