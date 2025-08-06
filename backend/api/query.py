"""
智能问答API
"""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from typing import List

from backend.models.schemas import QueryRequest, QueryResponse, ChatHistory, ChatMessage
from backend.services.qa_service import QAService
from backend.services.session_service import SessionService
from backend.core.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)

# 初始化服务
qa_service = QAService()
session_service = SessionService()

@router.post("/query", response_model=QueryResponse)
async def intelligent_qa(
    request: QueryRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    智能问答接口
    基于RAG系统回答用户问题
    """
    try:
        if not request.question.strip():
            raise HTTPException(
                status_code=400,
                detail="问题不能为空"
            )
        
        # 获取对话历史
        chat_history = []
        if request.use_history:
            chat_history = await session_service.get_chat_history(
                request.session_id, db
            )
        
        # 调用问答服务
        result = await qa_service.answer_question(
            question=request.question,
            session_id=request.session_id,
            chat_history=chat_history,
            db=db
        )
        
        # 保存对话记录
        await session_service.save_message(
            session_id=request.session_id,
            message_type="user",
            content=request.question,
            db=db
        )
        
        await session_service.save_message(
            session_id=request.session_id,
            message_type="assistant",
            content=result['answer'],
            db=db
        )
        
        logger.info(f"问答成功 - 会话: {request.session_id}, 问题: {request.question[:50]}...")
        
        return QueryResponse(
            answer=result['answer'],
            sources=result['sources'],
            confidence=result['confidence'],
            session_id=request.session_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"智能问答失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"问答服务异常: {str(e)}"
        )

@router.get("/history/{session_id}", response_model=ChatHistory)
async def get_chat_history(
    session_id: str,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """获取对话历史"""
    try:
        messages = await session_service.get_chat_history(
            session_id, db, limit
        )
        
        return ChatHistory(
            session_id=session_id,
            messages=messages
        )
        
    except Exception as e:
        logger.error(f"获取对话历史失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"获取对话历史异常: {str(e)}"
        )

@router.delete("/history/{session_id}")
async def clear_chat_history(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """清除对话历史"""
    try:
        await session_service.clear_chat_history(session_id, db)
        return {"message": "对话历史已清除"}
        
    except Exception as e:
        logger.error(f"清除对话历史失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"清除对话历史异常: {str(e)}"
        )

@router.post("/feedback")
async def submit_feedback(
    session_id: str,
    message_id: int,
    rating: int,
    comment: str = "",
    db: AsyncSession = Depends(get_db)
):
    """提交反馈"""
    try:
        if rating < 1 or rating > 5:
            raise HTTPException(
                status_code=400,
                detail="评分必须在1-5之间"
            )
        
        await session_service.save_feedback(
            session_id=session_id,
            message_id=message_id,
            rating=rating,
            comment=comment,
            db=db
        )
        
        return {"message": "反馈提交成功"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"提交反馈失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"提交反馈异常: {str(e)}"
        )