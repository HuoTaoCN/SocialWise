"""
语音处理服务 - 科大讯飞集成
"""
import asyncio
import base64
import json
import websockets
import hashlib
import hmac
import time
from urllib.parse import urlencode
from typing import Optional, AsyncGenerator
import aiofiles
import tempfile
import os

from backend.core.config import settings

class IFlytekVoiceService:
    """科大讯飞语音服务"""
    
    def __init__(self):
        self.app_id = settings.IFLYTEK_APP_ID
        self.api_key = settings.IFLYTEK_API_KEY
        self.api_secret = settings.IFLYTEK_API_SECRET
        
        # ASR配置
        self.asr_url = "wss://iat-api.xfyun.cn/v2/iat"
        
        # TTS配置
        self.tts_url = "wss://tts-api.xfyun.cn/v2/tts"
    
    def _generate_auth_url(self, url: str) -> str:
        """生成认证URL"""
        # 生成RFC1123格式的时间戳
        now = time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())
        
        # 拼接字符串
        signature_origin = f"host: ws-api.xfyun.cn\ndate: {now}\nGET /v2/iat HTTP/1.1"
        
        # 进行hmac-sha256进行加密
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        
        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')
        
        authorization_origin = f'api_key="{self.api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'
        
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        
        # 将请求的鉴权参数组合为字典
        v = {
            "authorization": authorization,
            "date": now,
            "host": "ws-api.xfyun.cn"
        }
        
        # 拼接鉴权参数，生成url
        url = url + '?' + urlencode(v)
        return url
    
    async def speech_to_text(self, audio_data: bytes) -> str:
        """语音转文字 (ASR)"""
        try:
            auth_url = self._generate_auth_url(self.asr_url)
            
            async with websockets.connect(auth_url) as websocket:
                # 发送开始参数
                start_params = {
                    "common": {
                        "app_id": self.app_id
                    },
                    "business": {
                        "language": "zh_cn",
                        "domain": "iat",
                        "accent": "mandarin",
                        "vad_eos": 10000,
                        "dwa": "wpgs"
                    },
                    "data": {
                        "status": 0,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": base64.b64encode(audio_data).decode()
                    }
                }
                
                await websocket.send(json.dumps(start_params))
                
                # 接收结果
                result_text = ""
                async for message in websocket:
                    data = json.loads(message)
                    if data.get("code") == 0:
                        if "data" in data:
                            result = data["data"]["result"]
                            if "ws" in result:
                                for ws in result["ws"]:
                                    for cw in ws["cw"]:
                                        result_text += cw["w"]
                    else:
                        raise Exception(f"ASR错误: {data.get('message', '未知错误')}")
                
                return result_text.strip()
                
        except Exception as e:
            raise Exception(f"语音识别失败: {str(e)}")
    
    async def text_to_speech(self, text: str, voice: str = "xiaoyan") -> bytes:
        """文字转语音 (TTS)"""
        try:
            auth_url = self._generate_auth_url(self.tts_url)
            
            async with websockets.connect(auth_url) as websocket:
                # 发送TTS参数
                tts_params = {
                    "common": {
                        "app_id": self.app_id
                    },
                    "business": {
                        "aue": "raw",
                        "auf": "audio/L16;rate=16000",
                        "vcn": voice,
                        "speed": 50,
                        "volume": 50,
                        "pitch": 50,
                        "bgs": 1,
                        "tte": "utf8"
                    },
                    "data": {
                        "status": 2,
                        "text": base64.b64encode(text.encode('utf-8')).decode()
                    }
                }
                
                await websocket.send(json.dumps(tts_params))
                
                # 接收音频数据
                audio_data = b""
                async for message in websocket:
                    data = json.loads(message)
                    if data.get("code") == 0:
                        if "data" in data:
                            audio_chunk = base64.b64decode(data["data"]["audio"])
                            audio_data += audio_chunk
                    else:
                        raise Exception(f"TTS错误: {data.get('message', '未知错误')}")
                
                return audio_data
                
        except Exception as e:
            raise Exception(f"语音合成失败: {str(e)}")

# 全局语音服务实例
voice_service = IFlytekVoiceService()