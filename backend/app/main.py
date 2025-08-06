"""
SocialWise 主应用入口
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
import uvicorn

from .config import settings
from .database import db_manager
from .logger import setup_logging
from .metrics import MetricsMiddleware, get_metrics, get_metrics_content_type
from .services.session_service import SessionService
from .services.speech_service import SpeechService
from .services.nlp_service import NLPService
from .services.knowledge_service import KnowledgeService

# 设置日志
setup_logging()
logger = logging.getLogger(__name__)

# 全局服务实例
session_service = None
speech_service = None
nlp_service = None
knowledge_service = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    global session_service, speech_service, nlp_service, knowledge_service
    
    try:
        logger.info("SocialWise 应用启动中...")
        
        # 初始化数据库
        await db_manager.initialize()
        
        # 初始化服务
        session_service = SessionService()
        await session_service.initialize()
        
        speech_service = SpeechService()
        await speech_service.initialize()
        
        nlp_service = NLPService()
        await nlp_service.initialize()
        
        knowledge_service = KnowledgeService()
        await knowledge_service.initialize()
        
        logger.info("SocialWise 应用启动完成")
        
        yield
        
    except Exception as e:
        logger.error(f"应用启动失败: {str(e)}")
        raise
    finally:
        # 清理资源
        logger.info("SocialWise 应用关闭中...")
        
        if session_service:
            await session_service.close()
        if knowledge_service:
            await knowledge_service.close()
        if db_manager:
            await db_manager.close()
        
        logger.info("SocialWise 应用已关闭")

# 创建FastAPI应用
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="社保智答 - 智能社会保障服务助手",
    lifespan=lifespan
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加监控中间件
app.add_middleware(MetricsMiddleware)

# 静态文件服务
app.mount("/static", StaticFiles(directory="static"), name="static")

# API路由

@app.get("/")
async def root():
    """根路径"""
    return {
        "message": "欢迎使用 SocialWise 社保智答",
        "version": settings.APP_VERSION,
        "status": "running"
    }

@app.post("/api/asr")
async def speech_to_text(audio: UploadFile = File(...)):
    """语音识别接口"""
    try:
        if not speech_service:
            raise HTTPException(status_code=503, detail="语音服务未初始化")
        
        # 读取音频数据
        audio_data = await audio.read()
        
        # 执行语音识别
        result = await speech_service.recognize_speech(audio_data)
        
        return {
            "success": True,
            "text": result.get("text", ""),
            "confidence": result.get("confidence", 0.0)
        }
        
    except Exception as e:
        logger.error(f"语音识别失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"语音识别失败: {str(e)}")

@app.post("/api/tts")
async def text_to_speech(text: str = Form(...)):
    """语音合成接口"""
    try:
        if not speech_service:
            raise HTTPException(status_code=503, detail="语音服务未初始化")
        
        # 执行语音合成
        audio_data = await speech_service.synthesize_speech(text)
        
        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers={"Content-Disposition": "attachment; filename=speech.wav"}
        )
        
    except Exception as e:
        logger.error(f"语音合成失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"语音合成失败: {str(e)}")

@app.post("/api/query")
async def intelligent_query(
    question: str = Form(...),
    session_id: str = Form(...)
):
    """智能问答接口"""
    try:
        if not nlp_service or not session_service:
            raise HTTPException(status_code=503, detail="服务未初始化")
        
        # 获取会话历史
        session_data = await session_service.get_session(session_id)
        chat_history = session_data.get("messages", [])
        
        # 执行智能查询
        result = await nlp_service.query(question, chat_history)
        
        # 保存对话记录
        await session_service.add_message(session_id, "user", question)
        await session_service.add_message(session_id, "assistant", result["answer"])
        
        return {
            "success": True,
            "answer": result["answer"],
            "confidence": result.get("confidence", 0.0),
            "sources": result.get("sources", []),
            "processing_time": result.get("processing_time", 0.0)
        }
        
    except Exception as e:
        logger.error(f"智能查询失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"智能查询失败: {str(e)}")

@app.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str):
    """获取聊天历史"""
    try:
        if not session_service:
            raise HTTPException(status_code=503, detail="会话服务未初始化")
        
        history = await session_service.get_session_history(session_id)
        
        return {
            "success": True,
            "history": history
        }
        
    except Exception as e:
        logger.error(f"获取聊天历史失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取聊天历史失败: {str(e)}")

@app.post("/api/feedback")
async def submit_feedback(
    session_id: str = Form(...),
    feedback_type: str = Form(...),
    rating: int = Form(None),
    comment: str = Form("")
):
    """提交用户反馈"""
    try:
        if not session_service:
            raise HTTPException(status_code=503, detail="会话服务未初始化")
        
        success = await session_service.save_user_feedback(
            session_id, feedback_type, rating, comment
        )
        
        return {
            "success": success,
            "message": "反馈提交成功" if success else "反馈提交失败"
        }
        
    except Exception as e:
        logger.error(f"提交反馈失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"提交反馈失败: {str(e)}")

@app.post("/api/documents/upload")
async def upload_document(file: UploadFile = File(...)):
    """上传文档到知识库"""
    try:
        if not knowledge_service:
            raise HTTPException(status_code=503, detail="知识库服务未初始化")
        
        # 保存上传的文件
        file_path = f"{settings.DOCUMENTS_DIR}/{file.filename}"
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        
        # 添加到知识库
        success = await knowledge_service.add_document(file_path)
        
        return {
            "success": success,
            "message": "文档上传成功" if success else "文档上传失败",
            "filename": file.filename
        }
        
    except Exception as e:
        logger.error(f"文档上传失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"文档上传失败: {str(e)}")

@app.get("/api/knowledge/search")
async def search_knowledge(q: str, limit: int = 5):
    """搜索知识库"""
    try:
        if not knowledge_service:
            raise HTTPException(status_code=503, detail="知识库服务未初始化")
        
        # 搜索文档
        doc_results = await knowledge_service.search_documents(q, limit)
        
        # 搜索FAQ
        faq_results = await knowledge_service.search_faq(q, limit)
        
        # 搜索可信问答
        qa_results = await knowledge_service.search_trusted_qa(q, limit)
        
        return {
            "success": True,
            "documents": doc_results,
            "faq": faq_results,
            "trusted_qa": qa_results
        }
        
    except Exception as e:
        logger.error(f"知识库搜索失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"知识库搜索失败: {str(e)}")

@app.get("/api/health")
async def health_check():
    """系统健康检查"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": "2024-01-01T00:00:00Z",
            "services": {}
        }
        
        # 检查各个服务
        if session_service:
            health_status["services"]["session"] = await session_service.health_check()
        
        if speech_service:
            health_status["services"]["speech"] = await speech_service.health_check()
        
        if nlp_service:
            health_status["services"]["nlp"] = await nlp_service.health_check()
        
        if knowledge_service:
            health_status["services"]["knowledge"] = await knowledge_service.health_check()
        
        return health_status
        
    except Exception as e:
        logger.error(f"健康检查失败: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@app.get("/metrics")
async def metrics():
    """Prometheus监控指标"""
    return Response(
        content=get_metrics(),
        media_type=get_metrics_content_type()
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )