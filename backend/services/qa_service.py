"""
智能问答服务
基于通义千问和RAG系统
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import dashscope
from dashscope import Generation
import json

from backend.core.config import settings
from backend.services.knowledge_service import KnowledgeService
from backend.models.schemas import ChatMessage, VectorSearchResult

logger = logging.getLogger(__name__)

# 配置通义千问
dashscope.api_key = settings.DASHSCOPE_API_KEY

class QAService:
    """智能问答服务类"""
    
    def __init__(self):
        self.knowledge_service = KnowledgeService()
        self.model = settings.QWEN_MODEL
        
        # 系统提示词
        self.system_prompt = """
你是"社保智答/SocialWise"智能助手，专门