"""
语音识别API
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
import logging
import asyncio
from io import BytesIO

from backend.models.schemas import ASRRequest, ASRResponse
from backend.services.speech_service import SpeechService
from backend.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

# 初始化语音服务
speech_service = SpeechService()

@router.post("/asr", response_model=ASRResponse)
async def speech_to_text(audio_file: UploadFile = File(...)):
    """
    语音识别接口
    将用户上传的音频文件转换为文本
    """
    try:
        # 验证文件类型
        if not audio_file.content_type.startswith('audio/'):
            raise HTTPException(
                status_code=400,
                detail="不支持的文件类型，请上传音频文件"
            )
        
        # 读取音频数据
        audio_data = await audio_file.read()
        
        if len(audio_data) == 0:
            raise HTTPException(
                status_code=400,
                detail="音频文件为空"
            )
        
        # 调用语音识别服务
        result = await speech_service.speech_to_text(
            audio_data=audio_data,
            format=audio_file.content_type.split('/')[-1]
        )
        
        logger.info(f"语音识别成功: {result['text'][:50]}...")
        
        return ASRResponse(
            text=result['text'],
            confidence=result['confidence']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"语音识别失败: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"语音识别服务异常: {str(e)}"
        )

@router.post("/asr/stream")
async def stream_speech_to_text(audio_file: UploadFile = File(...)):
    """
    流式语音识别接口
    支持实时语音识别
    """
    try:
        audio_data = await audio_file.read()
        
        # 流式识别
        async for partial_result in speech_service.stream_speech_to_text(audio_data):
            yield f"data: {partial_result}\n\n"
            
    except Exception as e:
        logger.error(f"流式语音识别失败: {e}")
        yield f"data: {{'error': '{str(e)}'}}\n\n"

@router.get("/asr/config")
async def get_asr_config():
    """获取语音识别配置"""
    return {
        "language": settings.ASR_LANGUAGE,
        "sample_rate": settings.AUDIO_SAMPLE_RATE,
        "supported_formats": ["wav", "mp3", "m4a", "flac"],
        "max_duration": 60  # 秒
    }