"""
语音合成API
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import logging
from io import BytesIO

from backend.models.schemas import TTSRequest, TTSResponse
from backend.services.speech_service import SpeechService
from backend.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# 初始化语音服务
speech_service = SpeechService()

@router.post("/tts")
async def text_to_speech(request: TTSRequest):
    """
    语音合成接口
    将文本转换为语音
    """
    try:
        if not request.text.strip():
            raise HTTPException(
                status_code=400,
                detail="文本内容不能为空"
            )
        
        if len(request.text) > 1000:
            raise HTTPException(
                status_code=400,
                detail="文本长度不能超过1000字符"
            )
        
        # 调用语音合成服务
        audio_data = await speech_service.text_to_speech(
            text=request.text,
            voice=request.voice,
            speed=request.speed
        )
        
        logger.info(f"语音合成成功: {request.text[:50]}...")
        
        # 返回音频流
        return StreamingResponse(
            BytesIO(audio_data),
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=speech.wav"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"语音合成失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"语音合成服务异常: {str(e)}"
        )

@router.post("/tts/stream")
async def stream_text_to_speech(request: TTSRequest):
    """
    流式语音合成接口
    支持实时语音合成
    """
    try:
        async def generate_audio():
            async for audio_chunk in speech_service.stream_text_to_speech(
                text=request.text,
                voice=request.voice,
                speed=request.speed
            ):
                yield audio_chunk
        
        return StreamingResponse(
            generate_audio(),
            media_type="audio/wav"
        )
        
    except Exception as e:
        logger.error(f"流式语音合成失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"流式语音合成服务异常: {str(e)}"
        )

@router.get("/tts/voices")
async def get_available_voices():
    """获取可用的音色列表"""
    return {
        "voices": [
            {"name": "xiaoyan", "description": "小燕 - 温柔女声"},
            {"name": "xiaoyu", "description": "小宇 - 清新男声"},
            {"name": "xiaoxin", "description": "小欣 - 甜美女声"},
            {"name": "xiaofeng", "description": "小峰 - 成熟男声"}
        ],
        "default_voice": settings.TTS_VOICE,
        "speed_range": [0.5, 2.0],
        "default_speed": settings.TTS_SPEED
    }