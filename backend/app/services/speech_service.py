"""
语音服务 - 讯飞语音ASR/TTS集成
"""

import asyncio
import logging
import base64
import hashlib
import hmac
import json
import time
import urllib.parse
import websockets
from typing import Dict, Any, Optional
import aiohttp
import wave
import io

from ..utils.config import settings

logger = logging.getLogger(__name__)

class SpeechService:
    """语音服务类"""
    
    def __init__(self):
        # 讯飞语音配置
        self.app_id = settings.IFLYTEK_APP_ID
        self.api_secret = settings.IFLYTEK_API_SECRET
        self.api_key = settings.IFLYTEK_API_KEY
        
        # ASR配置
        self.asr_url = "wss://iat-api.xfyun.cn/v2/iat"
        
        # TTS配置
        self.tts_url = "wss://tts-api.xfyun.cn/v2/tts"
        
        # 音频配置
        self.sample_rate = settings.AUDIO_SAMPLE_RATE
        self.audio_format = settings.AUDIO_FORMAT
        
        logger.info("语音服务初始化完成")
    
    async def initialize(self):
        """初始化语音服务"""
        try:
            # 验证配置
            if not all([self.app_id, self.api_secret, self.api_key]):
                logger.warning("讯飞语音配置不完整，语音功能可能无法正常使用")
            
            logger.info("语音服务初始化成功")
            
        except Exception as e:
            logger.error(f"语音服务初始化失败: {str(e)}")
            raise
    
    def _generate_auth_url(self, url: str) -> str:
        """生成认证URL"""
        try:
            # 解析URL
            parsed_url = urllib.parse.urlparse(url)
            host = parsed_url.netloc
            path = parsed_url.path
            
            # 生成时间戳
            now = time.time()
            date = time.strftime('%a, %d %b %Y %H:%M:%S %Z', time.gmtime(now))
            
            # 生成签名字符串
            signature_origin = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
            
            # 计算签名
            signature_sha = hmac.new(
                self.api_secret.encode('utf-8'),
                signature_origin.encode('utf-8'),
                digestmod=hashlib.sha256
            ).digest()
            signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')
            
            # 生成authorization
            authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'
            authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
            
            # 生成完整URL
            params = {
                'authorization': authorization,
                'date': date,
                'host': host
            }
            
            return f"{url}?" + urllib.parse.urlencode(params)
            
        except Exception as e:
            logger.error(f"生成认证URL失败: {str(e)}")
            raise
    
    async def recognize_speech(self, audio_data: str, audio_format: str = "wav", sample_rate: int = 16000) -> Dict[str, Any]:
        """语音识别"""
        try:
            # 解码音频数据
            audio_bytes = base64.b64decode(audio_data)
            
            # 生成认证URL
            auth_url = self._generate_auth_url(self.asr_url)
            
            # 准备识别参数
            params = {
                "common": {
                    "app_id": self.app_id
                },
                "business": {
                    "language": "zh_cn",
                    "domain": "iat",
                    "accent": "mandarin",
                    "vinfo": 1,
                    "vad_eos": 10000,
                    "sample_rate": sample_rate,
                    "audio_format": audio_format
                },
                "data": {
                    "status": 2,  # 一次性传输
                    "format": audio_format,
                    "encoding": "raw",
                    "audio": audio_data
                }
            }
            
            # 建立WebSocket连接并发送数据
            result_text = ""
            confidence = 0.0
            
            async with websockets.connect(auth_url) as websocket:
                # 发送识别参数
                await websocket.send(json.dumps(params))
                
                # 接收识别结果
                async for message in websocket:
                    response = json.loads(message)
                    
                    if response.get("code") != 0:
                        error_msg = response.get("message", "语音识别失败")
                        logger.error(f"ASR错误: {error_msg}")
                        return {"success": False, "error": error_msg}
                    
                    # 解析识别结果
                    data = response.get("data", {})
                    if data:
                        result = data.get("result", {})
                        if result:
                            ws_list = result.get("ws", [])
                            for ws in ws_list:
                                cw_list = ws.get("cw", [])
                                for cw in cw_list:
                                    result_text += cw.get("w", "")
                                    confidence = max(confidence, cw.get("sc", 0.0))
                    
                    # 检查是否结束
                    if response.get("data", {}).get("status") == 2:
                        break
            
            return {
                "success": True,
                "text": result_text.strip(),
                "confidence": confidence / 100.0 if confidence > 1 else confidence
            }
            
        except Exception as e:
            logger.error(f"语音识别失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def synthesize_speech(self, text: str, voice: str = "xiaoyan", speed: int = 50, volume: int = 50) -> Dict[str, Any]:
        """语音合成"""
        try:
            # 生成认证URL
            auth_url = self._generate_auth_url(self.tts_url)
            
            # 准备合成参数
            params = {
                "common": {
                    "app_id": self.app_id
                },
                "business": {
                    "aue": "raw",
                    "auf": "audio/L16;rate=16000",
                    "vcn": voice,
                    "speed": speed,
                    "volume": volume,
                    "pitch": 50,
                    "bgs": 0,
                    "tte": "UTF8"
                },
                "data": {
                    "status": 2,
                    "text": base64.b64encode(text.encode('utf-8')).decode('utf-8')
                }
            }
            
            # 建立WebSocket连接并发送数据
            audio_data = b""
            
            async with websockets.connect(auth_url) as websocket:
                # 发送合成参数
                await websocket.send(json.dumps(params))
                
                # 接收合成结果
                async for message in websocket:
                    response = json.loads(message)
                    
                    if response.get("code") != 0:
                        error_msg = response.get("message", "语音合成失败")
                        logger.error(f"TTS错误: {error_msg}")
                        return {"success": False, "error": error_msg}
                    
                    # 获取音频数据
                    data = response.get("data", {})
                    if data:
                        audio_chunk = data.get("audio")
                        if audio_chunk:
                            audio_data += base64.b64decode(audio_chunk)
                    
                    # 检查是否结束
                    if response.get("data", {}).get("status") == 2:
                        break
            
            # 转换为WAV格式
            wav_data = self._convert_to_wav(audio_data)
            
            return {
                "success": True,
                "audio_data": base64.b64encode(wav_data).decode('utf-8'),
                "format": "wav",
                "sample_rate": self.sample_rate
            }
            
        except Exception as e:
            logger.error(f"语音合成失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def _convert_to_wav(self, raw_audio: bytes) -> bytes:
        """将原始音频转换为WAV格式"""
        try:
            # 创建WAV文件
            wav_buffer = io.BytesIO()
            
            with wave.open(wav_buffer, 'wb') as wav_file:
                wav_file.setnchannels(1)  # 单声道
                wav_file.setsampwidth(2)  # 16位
                wav_file.setframerate(self.sample_rate)  # 采样率
                wav_file.writeframes(raw_audio)
            
            wav_buffer.seek(0)
            return wav_buffer.read()
            
        except Exception as e:
            logger.error(f"音频格式转换失败: {str(e)}")
            return raw_audio
    
    async def convert_audio_format(self, audio_data: bytes, source_format: str, target_format: str) -> bytes:
        """音频格式转换"""
        try:
            # 这里可以集成更复杂的音频处理库，如pydub
            # 目前简单返回原数据
            logger.info(f"音频格式转换: {source_format} -> {target_format}")
            return audio_data
            
        except Exception as e:
            logger.error(f"音频格式转换失败: {str(e)}")
            return audio_data
    
    async def validate_audio(self, audio_data: bytes, max_duration: int = None) -> Dict[str, Any]:
        """验证音频数据"""
        try:
            # 检查音频数据长度
            if len(audio_data) == 0:
                return {"valid": False, "error": "音频数据为空"}
            
            # 检查音频时长（简化实现）
            if max_duration:
                estimated_duration = len(audio_data) / (self.sample_rate * 2)  # 16位单声道
                if estimated_duration > max_duration:
                    return {"valid": False, "error": f"音频时长超过限制({max_duration}秒)"}
            
            return {"valid": True}
            
        except Exception as e:
            logger.error(f"音频验证失败: {str(e)}")
            return {"valid": False, "error": str(e)}
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            # 检查配置
            config_ok = all([self.app_id, self.api_secret, self.api_key])
            
            # 可以添加更多检查，如网络连接测试
            
            return {
                "config": config_ok,
                "asr_available": config_ok,
                "tts_available": config_ok
            }
            
        except Exception as e:
            logger.error(f"语音服务健康检查失败: {str(e)}")
            return {
                "config": False,
                "asr_available": False,
                "tts_available": False,
                "error": str(e)
            }
    
    async def close(self):
        """关闭语音服务"""
        try:
            # 清理资源
            logger.info("语音服务已关闭")
            
        except Exception as e:
            logger.error(f"关闭语音服务失败: {str(e)}")