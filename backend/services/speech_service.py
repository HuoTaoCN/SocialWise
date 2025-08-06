"""
语音处理服务
集成科大讯飞语音识别和合成
"""

import asyncio
import logging
import base64
import json
import websockets
import ssl
import hmac
import hashlib
from datetime import datetime
from urllib.parse import urlencode
from typing import AsyncGenerator, Dict, Any

from backend.core.config import settings

logger = logging.getLogger(__name__)

class SpeechService:
    """语音处理服务类"""
    
    def __init__(self):
        self.app_id = settings.IFLYTEK_APP_ID
        self.api_key = settings.IFLYTEK_API_KEY
        self.api_secret = settings.IFLYTEK_API_SECRET
        
        # 科大讯飞API配置
        self.asr_url = "wss://iat-api.xfyun.cn/v2/iat"
        self.tts_url = "wss://tts-api.xfyun.cn/v2/tts"
    
    def _generate_auth_url(self, base_url: str) -> str:
        """生成认证URL"""
        # 生成RFC1123格式的时间戳
        now = datetime.now()
        date = now.strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        # 拼接字符串
        signature_origin = f"host: ws-api.xfyun.cn\ndate: {date}\nGET /v2/iat HTTP/1.1"
        
        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')
        
        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        
        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        
        # 拼接鉴权参数，生成url
        url = base_url + '?' + urlencode(v)
        return url
    
    async def speech_to_text(self, audio_data: bytes, format: str = "wav") -> Dict[str, Any]:
        """
        语音识别
        """
        try:
            # 生成认证URL
            auth_url = self._generate_auth_url(self.asr_url)
            
            # WebSocket连接配置
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            result_text = ""
            confidence = 0.0
            
            async with websockets.connect(auth_url, ssl=ssl_context) as websocket:
                # 发送开始参数
                start_params = {
                    "common": {
                        "app_id": self.app_id
                    },
                    "business": {
                        "language": settings.ASR_LANGUAGE,
                        "domain": "iat",
                        "accent": "mandarin",
                        "vinfo": 1,
                        "vad_eos": 10000
                    },
                    "data": {
                        "status": 0,
                        "format": "audio/L16;rate=16000",
                        "audio": base64.b64encode(audio_data).decode(),
                        "encoding": "raw"
                    }
                }
                
                await websocket.send(json.dumps(start_params))
                
                # 发送结束标志
                end_params = {
                    "data": {
                        "status": 2,
                        "format": "audio/L16;rate=16000",
                        "audio": "",
                        "encoding": "raw"
                    }
                }
                await websocket.send(json.dumps(end_params))
                
                # 接收识别结果
                async for message in websocket:
                    data = json.loads(message)
                    
                    if data.get("code") != 0:
                        raise Exception(f"语音识别错误: {data.get('message', '未知错误')}")
                    
                    if "data" in data and "result" in data["data"]:
                        result = data["data"]["result"]
                        if "ws" in result:
                            for ws in result["ws"]:
                                for cw in ws["cw"]:
                                    result_text += cw["w"]
                                    confidence = max(confidence, cw.get("wp", 0) / 100.0)
                    
                    if data.get("data", {}).get("status") == 2:
                        break
            
            return {
                "text": result_text,
                "confidence": confidence
            }
            
        except Exception as e:
            logger.error(f"语音识别失败: {e}")
            raise
    
    async def stream_speech_to_text(self, audio_data: bytes) -> AsyncGenerator[str, None]:
        """
        流式语音识别
        """
        try:
            auth_url = self._generate_auth_url(self.asr_url)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with websockets.connect(auth_url, ssl=ssl_context) as websocket:
                # 分块发送音频数据
                chunk_size = 1280  # 每次发送1280字节
                
                for i in range(0, len(audio_data), chunk_size):
                    chunk = audio_data[i:i + chunk_size]
                    status = 0 if i == 0 else 1
                    if i + chunk_size >= len(audio_data):
                        status = 2
                    
                    params = {
                        "common": {
                            "app_id": self.app_id
                        },
                        "business": {
                            "language": settings.ASR_LANGUAGE,
                            "domain": "iat",
                            "accent": "mandarin"
                        },
                        "data": {
                            "status": status,
                            "format": "audio/L16;rate=16000",
                            "audio": base64.b64encode(chunk).decode(),
                            "encoding": "raw"
                        }
                    }
                    
                    await websocket.send(json.dumps(params))
                    
                    # 接收部分结果
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                        data = json.loads(message)
                        
                        if "data" in data and "result" in data["data"]:
                            result = data["data"]["result"]
                            if "ws" in result:
                                partial_text = ""
                                for ws in result["ws"]:
                                    for cw in ws["cw"]:
                                        partial_text += cw["w"]
                                
                                if partial_text:
                                    yield json.dumps({"text": partial_text, "final": status == 2})
                    
                    except asyncio.TimeoutError:
                        continue
                        
        except Exception as e:
            logger.error(f"流式语音识别失败: {e}")
            yield json.dumps({"error": str(e)})
    
    async def text_to_speech(self, text: str, voice: str = "xiaoyan", speed: float = 1.0) -> bytes:
        """
        语音合成
        """
        try:
            auth_url = self._generate_auth_url(self.tts_url)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            audio_data = b""
            
            async with websockets.connect(auth_url, ssl=ssl_context) as websocket:
                params = {
                    "common": {
                        "app_id": self.app_id
                    },
                    "business": {
                        "aue": "raw",
                        "auf": "audio/L16;rate=16000",
                        "vcn": voice,
                        "speed": int(speed * 50),
                        "volume": 50,
                        "pitch": 50,
                        "bgs": 0,
                        "tte": "UTF8"
                    },
                    "data": {
                        "status": 2,
                        "text": base64.b64encode(text.encode('utf-8')).decode()
                    }
                }
                
                await websocket.send(json.dumps(params))
                
                async for message in websocket:
                    data = json.loads(message)
                    
                    if data.get("code") != 0:
                        raise Exception(f"语音合成错误: {data.get('message', '未知错误')}")
                    
                    if "data" in data and "audio" in data["data"]:
                        audio_chunk = base64.b64decode(data["data"]["audio"])
                        audio_data += audio_chunk
                    
                    if data.get("data", {}).get("status") == 2:
                        break
            
            return audio_data
            
        except Exception as e:
            logger.error(f"语音合成失败: {e}")
            raise
    
    async def stream_text_to_speech(self, text: str, voice: str = "xiaoyan", speed: float = 1.0) -> AsyncGenerator[bytes, None]:
        """
        流式语音合成
        """
        try:
            auth_url = self._generate_auth_url(self.tts_url)
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            async with websockets.connect(auth_url, ssl=ssl_context) as websocket:
                params = {
                    "common": {
                        "app_id": self.app_id
                    },
                    "business": {
                        "aue": "raw",
                        "auf": "audio/L16;rate=16000",
                        "vcn": voice,
                        "speed": int(speed * 50),
                        "volume": 50,
                        "pitch": 50,
                        "bgs": 0,
                        "tte": "UTF8"
                    },
                    "data": {
                        "status": 2,
                        "text": base64.b64encode(text.encode('utf-8')).decode()
                    }
                }
                
                await websocket.send(json.dumps(params))
                
                async for message in websocket:
                    data = json.loads(message)
                    
                    if data.get("code") != 0:
                        raise Exception(f"语音合成错误: {data.get('message', '未知错误')}")
                    
                    if "data" in data and "audio" in data["data"]:
                        audio_chunk = base64.b64decode(data["data"]["audio"])
                        yield audio_chunk
                    
                    if data.get("data", {}).get("status") == 2:
                        break
                        
        except Exception as e:
            logger.error(f"流式语音合成失败: {e}")
            raise