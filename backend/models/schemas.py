"""
数据模型定义
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class MessageType(str, Enum):
    """消息类型"""
    USER = "user"
    ASSISTANT = "assistant"

class SourceType(str, Enum):
    """数据源类型"""
    FAQ = "faq"
    DOCUMENT = "document"
    TRUSTED_QA = "trusted_qa"

# 语音处理相关模型
class ASRRequest(BaseModel):
    """语音识别请求"""
    audio_data: bytes = Field(..., description="音频数据")
    format: str = Field(default="wav", description="音频格式")
    sample_rate: int = Field(default=16000, description="采样率")

class ASRResponse(BaseModel):
    """语音识别响应"""
    text: str = Field(..., description="识别的文本")
    confidence: float = Field(..., description="置信度")

class TTSRequest(BaseModel):
    """语音合成请求"""
    text: str = Field(..., description="待合成的文本")
    voice: str = Field(default="xiaoyan", description="音色")
    speed: float = Field(default=1.0, description="语速")

class TTSResponse(BaseModel):
    """语音合成响应"""
    audio_data: bytes = Field(..., description="合成的音频数据")
    format: str = Field(default="wav", description="音频格式")

# 问答相关模型
class QueryRequest(BaseModel):
    """问答请求"""
    question: str = Field(..., description="用户问题")
    session_id: str = Field(..., description="会话ID")
    use_history: bool = Field(default=True, description="是否使用历史对话")

class QueryResponse(BaseModel):
    """问答响应"""
    answer: str = Field(..., description="回答内容")
    sources: List[Dict[str, Any]] = Field(default=[], description="参考来源")
    confidence: float = Field(..., description="置信度")
    session_id: str = Field(..., description="会话ID")

class ChatMessage(BaseModel):
    """聊天消息"""
    type: MessageType = Field(..., description="消息类型")
    content: str = Field(..., description="消息内容")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")

class ChatHistory(BaseModel):
    """聊天历史"""
    session_id: str = Field(..., description="会话ID")
    messages: List[ChatMessage] = Field(default=[], description="消息列表")

# 知识库相关模型
class FAQItem(BaseModel):
    """FAQ项目"""
    id: Optional[int] = None
    question: str = Field(..., description="问题")
    answer: str = Field(..., description="答案")
    category: Optional[str] = Field(None, description="分类")
    keywords: List[str] = Field(default=[], description="关键词")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class TrustedQA(BaseModel):
    """可信QA对"""
    id: Optional[int] = None
    question: str = Field(..., description="问题")
    answer: str = Field(..., description="答案")
    source_type: SourceType = Field(..., description="来源类型")
    source_id: Optional[int] = Field(None, description="来源ID")
    confidence_score: float = Field(default=1.0, description="置信度分数")
    verified_by: Optional[str] = Field(None, description="验证人")
    verified_at: Optional[datetime] = Field(None, description="验证时间")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class DocumentInfo(BaseModel):
    """文档信息"""
    id: Optional[int] = None
    filename: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件路径")
    file_type: str = Field(..., description="文件类型")
    file_size: int = Field(..., description="文件大小")
    content_hash: Optional[str] = Field(None, description="内容哈希")
    processed: bool = Field(default=False, description="是否已处理")
    created_at: Optional[datetime] = None

class VectorSearchResult(BaseModel):
    """向量搜索结果"""
    text: str = Field(..., description="文本内容")
    score: float = Field(..., description="相似度分数")
    source_type: SourceType = Field(..., description="来源类型")
    source_id: int = Field(..., description="来源ID")
    metadata: Dict[str, Any] = Field(default={}, description="元数据")

# 系统监控相关模型
class SystemMetric(BaseModel):
    """系统指标"""
    metric_name: str = Field(..., description="指标名称")
    metric_value: float = Field(..., description="指标值")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")

class HealthStatus(BaseModel):
    """健康状态"""
    status: str = Field(..., description="状态")
    service: str = Field(..., description="服务名")
    timestamp: datetime = Field(default_factory=datetime.now, description="时间戳")
    details: Dict[str, Any] = Field(default={}, description="详细信息")

# 文件上传相关模型
class FileUploadResponse(BaseModel):
    """文件上传响应"""
    filename: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件路径")
    file_size: int = Field(..., description="文件大小")
    upload_time: datetime = Field(default_factory=datetime.now, description="上传时间")
    message: str = Field(..., description="响应消息")

class ProcessingStatus(BaseModel):
    """处理状态"""
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="状态")
    progress: float = Field(default=0.0, description="进度")
    message: str = Field(default="", description="状态消息")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")