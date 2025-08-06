"""
知识库数据模型
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.core.database import Base

class Document(Base):
    """原始文档表"""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)  # pdf, txt, docx
    file_size = Column(Integer)
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    processed = Column(Boolean, default=False)
    category = Column(String(100))
    description = Column(Text)
    
    # 关联的文档片段
    chunks = relationship("DocumentChunk", back_populates="document")

class DocumentChunk(Base):
    """文档片段表（用于向量检索）"""
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    chunk_text = Column(Text, nullable=False)
    chunk_index = Column(Integer)  # 在文档中的位置
    vector_id = Column(String(100))  # Milvus中的向量ID
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关联原始文档
    document = relationship("Document", back_populates="chunks")

class FAQ(Base):
    """FAQ表"""
    __tablename__ = "faq"
    
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    category = Column(String(100))
    keywords = Column(Text)  # 关键词，用于检索
    priority = Column(Integer, default=0)  # 优先级
    view_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)

class TrustedQA(Base):
    """可信问答对表（人工确认）"""
    __tablename__ = "trusted_qa"
    
    id = Column(Integer, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    source_type = Column(String(50))  # faq, document, generated
    source_id = Column(Integer)  # 来源ID
    confidence_score = Column(Float)  # 置信度
    human_verified = Column(Boolean, default=False)  # 人工确认
    verified_by = Column(String(100))  # 确认人
    verified_at = Column(DateTime(timezone=True))
    category = Column(String(100))
    tags = Column(Text)  # JSON格式的标签
    usage_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    is_active = Column(Boolean, default=True)

class ChatSession(Base):
    """对话会话表"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), unique=True, index=True)
    user_id = Column(String(100))  # 用户标识
    start_time = Column(DateTime(timezone=True), server_default=func.now())
    end_time = Column(DateTime(timezone=True))
    total_messages = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    
    # 关联的对话消息
    messages = relationship("ChatMessage", back_populates="session")

class ChatMessage(Base):
    """对话消息表"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(100), ForeignKey("chat_sessions.session_id"))
    message_type = Column(String(20))  # user, assistant, system
    content = Column(Text, nullable=False)
    audio_file = Column(String(500))  # 语音文件路径
    response_time = Column(Float)  # 响应时间（秒）
    confidence_score = Column(Float)  # 回答置信度
    source_info = Column(Text)  # JSON格式的来源信息
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 关联会话
    session = relationship("ChatSession", back_populates="messages")