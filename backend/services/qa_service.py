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
你是"社保智答/SocialWise"智能助手，专门回答社会保险相关问题。

你的职责：
1. 准确回答用户关于社保、医保、养老保险、失业保险、工伤保险、生育保险等问题
2. 提供政策解读、办事流程、缴费标准等实用信息
3. 语言要通俗易懂，避免过于专业的术语
4. 如果不确定答案，请明确告知用户并建议咨询相关部门

回答要求：
- 准确性：基于最新政策和法规
- 实用性：提供具体的操作指导
- 友好性：使用温和、专业的语气
- 简洁性：重点突出，条理清晰

如果用户问题超出社保范围，请礼貌地引导回到社保话题。
"""
    
    async def get_answer(self, question: str, session_id: str, db: AsyncSession) -> Dict[str, Any]:
        """
        获取问题答案
        
        Args:
            question: 用户问题
            session_id: 会话ID
            db: 数据库会话
            
        Returns:
            包含答案、置信度、来源等信息的字典
        """
        try:
            logger.info(f"处理问题: {question}")
            
            # 1. 知识库检索
            search_results = await self.knowledge_service.search_knowledge(
                query=question,
                top_k=5,
                db=db
            )
            
            # 2. 构建上下文
            context = self._build_context(search_results)
            
            # 3. 生成回答
            answer = await self._generate_answer(question, context)
            
            # 4. 计算置信度
            confidence = self._calculate_confidence(search_results, answer)
            
            # 5. 保存对话历史
            await self._save_chat_history(question, answer, session_id, db)
            
            return {
                "answer": answer,
                "confidence": confidence,
                "sources": [{"title": r.title, "score": r.score} for r in search_results],
                "session_id": session_id
            }
            
        except Exception as e:
            logger.error(f"问答处理失败: {str(e)}")
            return {
                "answer": "抱歉，我暂时无法回答您的问题，请稍后重试或联系人工客服。",
                "confidence": 0.0,
                "sources": [],
                "session_id": session_id
            }
    
    def _build_context(self, search_results: List[VectorSearchResult]) -> str:
        """构建上下文信息"""
        if not search_results:
            return "暂无相关知识库信息。"
        
        context_parts = []
        for i, result in enumerate(search_results[:3], 1):
            context_parts.append(f"参考资料{i}：{result.content}")
        
        return "\n\n".join(context_parts)
    
    async def _generate_answer(self, question: str, context: str) -> str:
        """使用通义千问生成答案"""
        try:
            prompt = f"""
{self.system_prompt}

参考信息：
{context}

用户问题：{question}

请基于参考信息回答用户问题。如果参考信息不足，请基于你的知识给出合理回答，并提醒用户验证信息的准确性。
"""
            
            response = Generation.call(
                model=self.model,
                prompt=prompt,
                max_tokens=1000,
                temperature=0.3,
                top_p=0.8
            )
            
            if response.status_code == 200:
                return response.output.text.strip()
            else:
                logger.error(f"通义千问调用失败: {response.message}")
                return "抱歉，AI服务暂时不可用，请稍后重试。"
                
        except Exception as e:
            logger.error(f"生成答案失败: {str(e)}")
            return "抱歉，生成答案时出现错误，请稍后重试。"
    
    def _calculate_confidence(self, search_results: List[VectorSearchResult], answer: str) -> float:
        """计算回答置信度"""
        if not search_results:
            return 0.3  # 无知识库支持时的基础置信度
        
        # 基于检索结果的相似度计算置信度
        avg_score = sum(r.score for r in search_results) / len(search_results)
        
        # 置信度计算逻辑
        if avg_score > 0.8:
            confidence = 0.9
        elif avg_score > 0.6:
            confidence = 0.7
        elif avg_score > 0.4:
            confidence = 0.5
        else:
            confidence = 0.3
        
        return confidence
    
    async def _save_chat_history(self, question: str, answer: str, session_id: str, db: AsyncSession):
        """保存对话历史"""
        try:
            # 这里应该保存到数据库，暂时用日志记录
            logger.info(f"保存对话历史 - 会话:{session_id}, 问题:{question[:50]}...")
            
            # TODO: 实现数据库保存逻辑
            # chat_record = ChatHistory(
            #     session_id=session_id,
            #     question=question,
            #     answer=answer,
            #     created_at=datetime.utcnow()
            # )
            # db.add(chat_record)
            # await db.commit()
            
        except Exception as e:
            logger.error(f"保存对话历史失败: {str(e)}")
    
    async def get_chat_history(self, session_id: str, db: AsyncSession) -> List[ChatMessage]:
        """获取对话历史"""
        try:
            # TODO: 从数据库获取对话历史
            # 暂时返回空列表
            return []
            
        except Exception as e:
            logger.error(f"获取对话历史失败: {str(e)}")
            return []
    
    async def clear_chat_history(self, session_id: str, db: AsyncSession) -> bool:
        """清除对话历史"""
        try:
            # TODO: 实现清除对话历史的逻辑
            logger.info(f"清除会话历史: {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"清除对话历史失败: {str(e)}")
            return False