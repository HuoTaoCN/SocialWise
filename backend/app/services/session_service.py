"""
会话管理服务 - Redis + PostgreSQL
"""

import asyncio
import logging
import json
import redis.asyncio as redis
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid

from ..models.database import get_db_connection
from ..utils.config import settings

logger = logging.getLogger(__name__)

class SessionService:
    """会话管理服务"""
    
    def __init__(self):
        # Redis连接配置
        self.redis_client = None
        self.session_timeout = 3600  # 1小时超时
        
        logger.info("会话管理服务初始化完成")
    
    async def initialize(self):
        """初始化Redis连接"""
        try:
            self.redis_client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                password=settings.REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            
            # 测试连接
            await self.redis_client.ping()
            logger.info("Redis连接成功")
            
        except Exception as e:
            logger.error(f"Redis连接失败: {str(e)}")
            raise
    
    async def get_or_create_session(self, session_id: str, user_id: str = None) -> Dict[str, Any]:
        """获取或创建会话"""
        try:
            if not self.redis_client:
                await self.initialize()
            
            # 从Redis获取会话
            session_key = f"session:{session_id}"
            session_data = await self.redis_client.get(session_key)
            
            if session_data:
                session = json.loads(session_data)
                # 更新最后活跃时间
                session["last_active"] = datetime.now().isoformat()
                await self.redis_client.setex(
                    session_key, 
                    self.session_timeout, 
                    json.dumps(session)
                )
                return session
            else:
                # 创建新会话
                session = {
                    "session_id": session_id,
                    "user_id": user_id,
                    "created_at": datetime.now().isoformat(),
                    "last_active": datetime.now().isoformat(),
                    "history": [],
                    "context": {},
                    "message_count": 0
                }
                
                await self.redis_client.setex(
                    session_key,
                    self.session_timeout,
                    json.dumps(session)
                )
                
                # 同时在PostgreSQL中记录会话
                await self._save_session_to_db(session)
                
                logger.info(f"创建新会话: {session_id}")
                return session
                
        except Exception as e:
            logger.error(f"获取会话失败: {str(e)}")
            # 返回默认会话
            return {
                "session_id": session_id,
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "history": [],
                "context": {},
                "message_count": 0
            }
    
    async def add_message(self, session_id: str, role: str, content: str, metadata: Dict = None) -> bool:
        """添加消息到会话历史"""
        try:
            session = await self.get_or_create_session(session_id)
            
            message = {
                "role": role,  # user, assistant, system
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            }
            
            # 添加到历史记录
            session["history"].append(message)
            session["message_count"] += 1
            session["last_active"] = datetime.now().isoformat()
            
            # 保持最近20条消息
            if len(session["history"]) > 20:
                session["history"] = session["history"][-20:]
            
            # 更新Redis
            session_key = f"session:{session_id}"
            await self.redis_client.setex(
                session_key,
                self.session_timeout,
                json.dumps(session)
            )
            
            # 保存到PostgreSQL
            await self._save_message_to_db(session_id, message)
            
            return True
            
        except Exception as e:
            logger.error(f"添加消息失败: {str(e)}")
            return False
    
    async def get_session_history(self, session_id: str, limit: int = 10) -> List[Dict]:
        """获取会话历史"""
        try:
            session = await self.get_or_create_session(session_id)
            history = session.get("history", [])
            
            # 返回最近的消息
            return history[-limit:] if len(history) > limit else history
            
        except Exception as e:
            logger.error(f"获取会话历史失败: {str(e)}")
            return []
    
    async def update_session_context(self, session_id: str, context: Dict) -> bool:
        """更新会话上下文"""
        try:
            session = await self.get_or_create_session(session_id)
            session["context"].update(context)
            session["last_active"] = datetime.now().isoformat()
            
            # 更新Redis
            session_key = f"session:{session_id}"
            await self.redis_client.setex(
                session_key,
                self.session_timeout,
                json.dumps(session)
            )
            
            return True
            
        except Exception as e:
            logger.error(f"更新会话上下文失败: {str(e)}")
            return False
    
    async def save_feedback(self, session_id: str, rating: int, comment: str = "") -> bool:
        """保存用户反馈"""
        try:
            async with get_db_connection() as conn:
                query = """
                INSERT INTO user_feedback (session_id, rating, comment, created_at)
                VALUES ($1, $2, $3, $4)
                """
                await conn.execute(query, session_id, rating, comment, datetime.now())
                
            logger.info(f"保存用户反馈: {session_id}, 评分: {rating}")
            return True
            
        except Exception as e:
            logger.error(f"保存用户反馈失败: {str(e)}")
            return False
    
    async def get_system_metrics(self) -> Dict[str, Any]:
        """获取系统指标"""
        try:
            async with get_db_connection() as conn:
                # 今日会话数
                today_sessions = await conn.fetchval("""
                    SELECT COUNT(*) FROM chat_sessions 
                    WHERE DATE(created_at) = CURRENT_DATE
                """)
                
                # 今日消息数
                today_messages = await conn.fetchval("""
                    SELECT COUNT(*) FROM chat_messages 
                    WHERE DATE(created_at) = CURRENT_DATE
                """)
                
                # 平均评分
                avg_rating = await conn.fetchval("""
                    SELECT AVG(rating) FROM user_feedback 
                    WHERE created_at >= NOW() - INTERVAL '7 days'
                """) or 0
                
                # 活跃会话数（Redis）
                active_sessions = 0
                if self.redis_client:
                    keys = await self.redis_client.keys("session:*")
                    active_sessions = len(keys)
                
                return {
                    "today_sessions": today_sessions,
                    "today_messages": today_messages,
                    "active_sessions": active_sessions,
                    "avg_rating": round(float(avg_rating), 2),
                    "timestamp": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"获取系统指标失败: {str(e)}")
            return {
                "today_sessions": 0,
                "today_messages": 0,
                "active_sessions": 0,
                "avg_rating": 0.0,
                "timestamp": datetime.now().isoformat()
            }
    
    async def cleanup_expired_sessions(self):
        """清理过期会话"""
        try:
            if not self.redis_client:
                return
            
            # Redis会自动过期，这里主要清理数据库中的旧数据
            async with get_db_connection() as conn:
                # 删除30天前的消息
                await conn.execute("""
                    DELETE FROM chat_messages 
                    WHERE created_at < NOW() - INTERVAL '30 days'
                """)
                
                # 删除7天前的会话（保留有反馈的会话）
                await conn.execute("""
                    DELETE FROM chat_sessions 
                    WHERE created_at < NOW() - INTERVAL '7 days'
                    AND session_id NOT IN (
                        SELECT DISTINCT session_id FROM user_feedback
                    )
                """)
                
            logger.info("清理过期会话完成")
            
        except Exception as e:
            logger.error(f"清理过期会话失败: {str(e)}")
    
    async def _save_session_to_db(self, session: Dict):
        """保存会话到数据库"""
        try:
            async with get_db_connection() as conn:
                query = """
                INSERT INTO chat_sessions (session_id, user_id, created_at, last_active)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (session_id) DO UPDATE SET
                last_active = EXCLUDED.last_active
                """
                await conn.execute(
                    query,
                    session["session_id"],
                    session.get("user_id"),
                    datetime.fromisoformat(session["created_at"]),
                    datetime.fromisoformat(session["last_active"])
                )
                
        except Exception as e:
            logger.error(f"保存会话到数据库失败: {str(e)}")
    
    async def _save_message_to_db(self, session_id: str, message: Dict):
        """保存消息到数据库"""
        try:
            async with get_db_connection() as conn:
                query = """
                INSERT INTO chat_messages (session_id, role, content, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5)
                """
                await conn.execute(
                    query,
                    session_id,
                    message["role"],
                    message["content"],
                    json.dumps(message.get("metadata", {})),
                    datetime.fromisoformat(message["timestamp"])
                )
                
        except Exception as e:
            logger.error(f"保存消息到数据库失败: {str(e)}")
    
    async def close(self):
        """关闭连接"""
        if self.redis_client:
            await self.redis_client.close()