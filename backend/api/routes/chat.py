"""
智能问答API路由
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Dict, Optional
import uuid
from datetime import datetime

from backend.services.llm_service import llm_service
from backend.models.knowledge import ChatSession, ChatMessage
from backend.core.database import get_db, SessionLocal

router = APIRouter()

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None

class ChatResponse(BaseModel):
    answer: str
    session_id: str
    confidence: float
    sources: List[Dict]
    response_time: float

@router.post("/query", response_model=ChatResponse)
async def chat_query(request: ChatRequest, db: SessionLocal = Depends(get_db)):
    """智能问答"""
    try:
        start_time = datetime.now()
        
        # 获取或创建会话
        session_id = request.session_id or str(uuid.uuid4())
        session = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        
        if not session:
            session = ChatSession(
                session_id=session_id,
                user_id=request.user_id or "anonymous"
            )
            db.add(session)
            db.commit()
        
        # 获取历史对话
        history = []
        recent_messages = db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.desc()).limit(10).all()
        
        for msg in reversed(recent_messages):
            role = "user" if msg.message_type == "user" else "assistant"
            history.append({"role": role, "content": msg.content})
        
        # 搜索知识库
        knowledge_results = await llm_service.search_knowledge(request.question)
        
        # 构建上下文
        context = ""
        sources = []
        for result in knowledge_results:
            if result["type"] == "trusted_qa":
                context += f"问题：{result['question']}\n答案：{result['answer']}\n\n"
            elif result["type"] == "faq":
                context += f"FAQ：{result['question']}\n答案：{result['answer']}\n\n"
            elif result["type"] == "document":
                context += f"文档内容：{result['content']}\n\n"
            
            sources.append({
                "type": result["type"],
                "content": result.get("question", result.get("content", "")),
                "confidence": result["confidence"],
                "source": result["source"]
            })
        
        # 生成回答
        answer, confidence = await llm_service.generate_response(
            request.question, context, history
        )
        
        # 计算响应时间
        response_time = (datetime.now() - start_time).total_seconds()
        
        # 保存对话记录
        user_message = ChatMessage(
            session_id=session_id,
            message_type="user",
            content=request.question,
            response_time=response_time
        )
        
        assistant_message = ChatMessage(
            session_id=session_id,
            message_type="assistant",
            content=answer,
            confidence_score=confidence,
            source_info=str(sources)
        )
        
        db.add(user_message)
        db.add(assistant_message)
        
        # 更新会话统计
        session.total_messages += 2
        db.commit()
        
        return ChatResponse(
            answer=answer,
            session_id=session_id,
            confidence=confidence,
            sources=sources,
            response_time=response_time
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"问答处理失败: {str(e)}")

@router.get("/sessions/{session_id}/history")
async def get_chat_history(session_id: str, db: SessionLocal = Depends(get_db)):
    """获取对话历史"""
    messages = db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).order_by(ChatMessage.created_at).all()
    
    history = []
    for msg in messages:
        history.append({
            "type": msg.message_type,
            "content": msg.content,
            "timestamp": msg.created_at.isoformat(),
            "confidence": msg.confidence_score
        })
    
    return {"session_id": session_id, "history": history}

@router.delete("/sessions/{session_id}")
async def clear_session(session_id: str, db: SessionLocal = Depends(get_db)):
    """清除会话"""
    # 删除消息
    db.query(ChatMessage).filter(
        ChatMessage.session_id == session_id
    ).delete()
    
    # 删除会话
    db.query(ChatSession).filter(
        ChatSession.session_id == session_id
    ).delete()
    
    db.commit()
    
    return {"message": "会话已清除"}