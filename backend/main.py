"""
SocialWise 主应用入口
社保智答实时智能语音问答机器人
"""
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from contextlib import asynccontextmanager
import uvicorn
import logging
from pathlib import Path

from backend.api import asr, tts, query, knowledge
from backend.core.config import settings
from backend.core.database import init_db
from backend.services.monitoring import setup_prometheus_metrics

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时初始化
    logger.info("启动 SocialWise 应用...")
    await init_db()
    setup_prometheus_metrics()
    yield
    # 关闭时清理
    logger.info("关闭 SocialWise 应用...")

# 创建FastAPI应用
app = FastAPI(
    title="社保智答 / SocialWise",
    description="实时智能语音问答机器人 - 专注社会保障与福利服务",
    version="1.0.0",
    lifespan=lifespan
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态文件服务
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# 模板引擎
templates = Jinja2Templates(directory="frontend/templates")

# 注册API路由
app.include_router(asr.router, prefix="/api", tags=["语音识别"])
app.include_router(tts.router, prefix="/api", tags=["语音合成"])
app.include_router(query.router, prefix="/api", tags=["智能问答"])
app.include_router(knowledge.router, prefix="/api", tags=["知识库管理"])

@app.get("/", response_class=HTMLResponse)
async def root():
    """主页面"""
    return """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>社保智答 / SocialWise</title>
        <link rel="stylesheet" href="/static/css/main.css">
    </head>
    <body>
        <div class="container">
            <header class="header">
                <div class="logo">
                    <h1>社保智答 / SocialWise</h1>
                    <p>您的智能社保助手</p>
                </div>
            </header>
            
            <main class="main-content">
                <div class="chat-container">
                    <div id="chat-messages" class="chat-messages"></div>
                    <div class="input-area">
                        <button id="voice-btn" class="voice-btn">🎤 点击说话</button>
                        <input type="text" id="text-input" placeholder="或输入您的问题..." />
                        <button id="send-btn" class="send-btn">发送</button>
                    </div>
                </div>
            </main>
        </div>
        
        <script src="https://cdn.jsdelivr.net/npm/webrtc-adapter@8.2.3/out/adapter.js"></script>
        <script src="/static/js/main.js"></script>
    </body>
    </html>
    """

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "SocialWise"}

@app.get("/metrics")
async def metrics():
    """Prometheus指标"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return StreamingResponse(
        iter([generate_latest()]),
        media_type=CONTENT_TYPE_LATEST
    )

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info"
    )