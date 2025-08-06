"""
知识库管理服务 - PostgreSQL + Milvus向量数据库
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
import json
import os
import hashlib
from datetime import datetime
import asyncpg
from pymilvus import connections, Collection, FieldSchema, CollectionSchema, DataType, utility
import numpy as np
from sentence_transformers import SentenceTransformer
import PyPDF2
import docx
import re

from ..utils.config import settings
from ..utils.database import get_db_connection

logger = logging.getLogger(__name__)

class KnowledgeService:
    """知识库管理服务"""
    
    def __init__(self):
        # 数据库连接池
        self.db_pool = None
        
        # Milvus连接
        self.milvus_client = None
        self.collection_name = "socialwise_documents"
        self.collection = None
        
        # 文本嵌入模型
        self.embedding_model = None
        self.embedding_dim = 384  # all-MiniLM-L6-v2的维度
        
        # 文档处理配置
        self.max_chunk_size = 500  # 文档分块大小
        self.chunk_overlap = 50    # 分块重叠
        
        logger.info("知识库管理服务初始化完成")
    
    async def initialize(self):
        """初始化数据库连接和Milvus"""
        try:
            # 初始化PostgreSQL连接池
            self.db_pool = await asyncpg.create_pool(
                host=settings.POSTGRES_HOST,
                port=settings.POSTGRES_PORT,
                user=settings.POSTGRES_USER,
                password=settings.POSTGRES_PASSWORD,
                database=settings.POSTGRES_DB,
                min_size=5,
                max_size=20
            )
            
            # 初始化Milvus连接
            await self._connect_milvus()
            
            # 初始化嵌入模型
            self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
            
            logger.info("知识库服务初始化成功")
            
        except Exception as e:
            logger.error(f"知识库服务初始化失败: {str(e)}")
            raise
    
    async def _connect_milvus(self):
        """连接Milvus向量数据库"""
        try:
            # 连接Milvus
            connections.connect(
                alias="default",
                host=settings.MILVUS_HOST,
                port=settings.MILVUS_PORT
            )
            
            # 检查集合是否存在，不存在则创建
            if not utility.has_collection(self.collection_name):
                await self._create_collection()
            
            # 加载集合
            self.collection = Collection(self.collection_name)
            self.collection.load()
            
            logger.info("Milvus连接成功")
            
        except Exception as e:
            logger.error(f"Milvus连接失败: {str(e)}")
            raise
    
    async def _create_collection(self):
        """创建Milvus集合"""
        try:
            # 定义字段
            fields = [
                FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
                FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
                FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=2000),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=self.embedding_dim),
                FieldSchema(name="metadata", dtype=DataType.VARCHAR, max_length=1000)
            ]
            
            # 创建集合schema
            schema = CollectionSchema(fields, "SocialWise文档向量集合")
            
            # 创建集合
            collection = Collection(self.collection_name, schema)
            
            # 创建索引
            index_params = {
                "metric_type": "IP",  # 内积
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            collection.create_index("embedding", index_params)
            
            logger.info("Milvus集合创建成功")
            
        except Exception as e:
            logger.error(f"创建Milvus集合失败: {str(e)}")
            raise
    
    async def add_document(self, file_path: str, document_type: str = "raw", metadata: Optional[Dict] = None) -> bool:
        """添加文档到知识库"""
        try:
            # 读取文档内容
            content = await self._extract_document_content(file_path)
            if not content:
                logger.warning(f"文档内容为空: {file_path}")
                return False
            
            # 生成文档ID
            document_id = hashlib.md5(file_path.encode()).hexdigest()
            
            # 保存文档信息到PostgreSQL
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO documents (id, filename, file_path, document_type, content, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    ON CONFLICT (id) DO UPDATE SET
                        content = EXCLUDED.content,
                        metadata = EXCLUDED.metadata,
                        updated_at = CURRENT_TIMESTAMP
                """, document_id, os.path.basename(file_path), file_path, document_type, 
                    content, json.dumps(metadata or {}), datetime.now())
            
            # 文档分块
            chunks = self._split_document(content)
            
            # 生成嵌入向量并存储到Milvus
            await self._store_document_chunks(document_id, chunks, metadata)
            
            logger.info(f"文档添加成功: {file_path}, 分块数: {len(chunks)}")
            return True
            
        except Exception as e:
            logger.error(f"添加文档失败: {str(e)}")
            return False
    
    async def _extract_document_content(self, file_path: str) -> str:
        """提取文档内容"""
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.pdf':
                return await self._extract_pdf_content(file_path)
            elif file_ext == '.docx':
                return await self._extract_docx_content(file_path)
            elif file_ext == '.txt':
                return await self._extract_txt_content(file_path)
            else:
                logger.warning(f"不支持的文件格式: {file_ext}")
                return ""
                
        except Exception as e:
            logger.error(f"提取文档内容失败: {str(e)}")
            return ""
    
    async def _extract_pdf_content(self, file_path: str) -> str:
        """提取PDF内容"""
        try:
            content = ""
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                for page in pdf_reader.pages:
                    content += page.extract_text() + "\n"
            return content.strip()
            
        except Exception as e:
            logger.error(f"提取PDF内容失败: {str(e)}")
            return ""
    
    async def _extract_docx_content(self, file_path: str) -> str:
        """提取DOCX内容"""
        try:
            doc = docx.Document(file_path)
            content = ""
            for paragraph in doc.paragraphs:
                content += paragraph.text + "\n"
            return content.strip()
            
        except Exception as e:
            logger.error(f"提取DOCX内容失败: {str(e)}")
            return ""
    
    async def _extract_txt_content(self, file_path: str) -> str:
        """提取TXT内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                return file.read().strip()
                
        except Exception as e:
            logger.error(f"提取TXT内容失败: {str(e)}")
            return ""
    
    def _split_document(self, content: str) -> List[str]:
        """文档分块"""
        try:
            # 按段落分割
            paragraphs = content.split('\n\n')
            chunks = []
            current_chunk = ""
            
            for paragraph in paragraphs:
                paragraph = paragraph.strip()
                if not paragraph:
                    continue
                
                # 如果当前块加上新段落超过最大长度，保存当前块
                if len(current_chunk) + len(paragraph) > self.max_chunk_size:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                        # 保留重叠部分
                        overlap_text = current_chunk[-self.chunk_overlap:] if len(current_chunk) > self.chunk_overlap else current_chunk
                        current_chunk = overlap_text + " " + paragraph
                    else:
                        current_chunk = paragraph
                else:
                    current_chunk += " " + paragraph if current_chunk else paragraph
            
            # 添加最后一个块
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            return chunks
            
        except Exception as e:
            logger.error(f"文档分块失败: {str(e)}")
            return [content]  # 返回原始内容作为单个块
    
    async def _store_document_chunks(self, document_id: str, chunks: List[str], metadata: Optional[Dict] = None):
        """存储文档块到Milvus"""
        try:
            # 生成嵌入向量
            embeddings = self.embedding_model.encode(chunks)
            
            # 准备数据
            data = []
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                chunk_id = f"{document_id}_{i}"
                data.append({
                    "document_id": document_id,
                    "chunk_id": chunk_id,
                    "content": chunk,
                    "embedding": embedding.tolist(),
                    "metadata": json.dumps(metadata or {})
                })
            
            # 插入到Milvus
            self.collection.insert(data)
            self.collection.flush()
            
            logger.info(f"文档块存储成功: {document_id}, 块数: {len(chunks)}")
            
        except Exception as e:
            logger.error(f"存储文档块失败: {str(e)}")
            raise
    
    async def search_documents(self, query: str, limit: int = 5, score_threshold: float = 0.7) -> List[Dict[str, Any]]:
        """向量搜索文档"""
        try:
            # 生成查询向量
            query_embedding = self.embedding_model.encode([query])[0]
            
            # 搜索参数
            search_params = {"metric_type": "IP", "params": {"nprobe": 10}}
            
            # 执行搜索
            results = self.collection.search(
                data=[query_embedding.tolist()],
                anns_field="embedding",
                param=search_params,
                limit=limit,
                output_fields=["document_id", "chunk_id", "content", "metadata"]
            )
            
            # 处理结果
            search_results = []
            for hits in results:
                for hit in hits:
                    if hit.score >= score_threshold:
                        search_results.append({
                            "document_id": hit.entity.get("document_id"),
                            "chunk_id": hit.entity.get("chunk_id"),
                            "content": hit.entity.get("content"),
                            "score": hit.score,
                            "metadata": json.loads(hit.entity.get("metadata", "{}"))
                        })
            
            return search_results
            
        except Exception as e:
            logger.error(f"文档搜索失败: {str(e)}")
            return []
    
    async def search_faq(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """搜索FAQ"""
        try:
            async with self.db_pool.acquire() as conn:
                results = await conn.fetch("""
                    SELECT id, question, answer, category, tags, created_at
                    FROM faq
                    WHERE question ILIKE $1 OR answer ILIKE $1
                    ORDER BY 
                        CASE 
                            WHEN question ILIKE $1 THEN 1
                            WHEN answer ILIKE $1 THEN 2
                            ELSE 3
                        END,
                        created_at DESC
                    LIMIT $2
                """, f"%{query}%", limit)
                
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"FAQ搜索失败: {str(e)}")
            return []
    
    async def search_trusted_qa(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """搜索可信问答对"""
        try:
            async with self.db_pool.acquire() as conn:
                results = await conn.fetch("""
                    SELECT id, question, answer, source, confidence_score, tags, created_at
                    FROM trusted_qa
                    WHERE (question ILIKE $1 OR answer ILIKE $1) AND is_verified = true
                    ORDER BY 
                        confidence_score DESC,
                        CASE 
                            WHEN question ILIKE $1 THEN 1
                            WHEN answer ILIKE $1 THEN 2
                            ELSE 3
                        END,
                        created_at DESC
                    LIMIT $2
                """, f"%{query}%", limit)
                
                return [dict(row) for row in results]
                
        except Exception as e:
            logger.error(f"可信问答搜索失败: {str(e)}")
            return []
    
    async def save_generated_qa(self, question: str, answer: str, source: str, confidence_score: float, metadata: Optional[Dict] = None) -> bool:
        """保存生成的问答对"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO generated_qa (question, answer, source, confidence_score, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6)
                """, question, answer, source, confidence_score, json.dumps(metadata or {}), datetime.now())
                
            return True
            
        except Exception as e:
            logger.error(f"保存生成问答失败: {str(e)}")
            return False
    
    async def verify_qa_pair(self, qa_id: int, is_verified: bool, verifier: str, notes: str = "") -> bool:
        """验证问答对"""
        try:
            async with self.db_pool.acquire() as conn:
                await conn.execute("""
                    UPDATE generated_qa 
                    SET is_verified = $1, verifier = $2, verification_notes = $3, verified_at = $4
                    WHERE id = $5
                """, is_verified, verifier, notes, datetime.now(), qa_id)
                
                # 如果验证通过，移动到trusted_qa表
                if is_verified:
                    qa_data = await conn.fetchrow("""
                        SELECT question, answer, source, confidence_score, metadata
                        FROM generated_qa WHERE id = $1
                    """, qa_id)
                    
                    if qa_data:
                        await conn.execute("""
                            INSERT INTO trusted_qa (question, answer, source, confidence_score, tags, is_verified, created_at)
                            VALUES ($1, $2, $3, $4, $5, true, $6)
                        """, qa_data['question'], qa_data['answer'], qa_data['source'], 
                            qa_data['confidence_score'], json.dumps(qa_data.get('metadata', {})), datetime.now())
                
            return True
            
        except Exception as e:
            logger.error(f"验证问答对失败: {str(e)}")
            return False
    
    async def get_knowledge_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        try:
            async with self.db_pool.acquire() as conn:
                # 文档统计
                doc_stats = await conn.fetchrow("SELECT COUNT(*) as count FROM documents")
                
                # FAQ统计
                faq_stats = await conn.fetchrow("SELECT COUNT(*) as count FROM faq")
                
                # 可信问答统计
                trusted_qa_stats = await conn.fetchrow("SELECT COUNT(*) as count FROM trusted_qa WHERE is_verified = true")
                
                # 生成问答统计
                generated_qa_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(CASE WHEN is_verified = true THEN 1 END) as verified,
                        COUNT(CASE WHEN is_verified = false THEN 1 END) as rejected,
                        COUNT(CASE WHEN is_verified IS NULL THEN 1 END) as pending
                    FROM generated_qa
                """)
            
            # Milvus统计
            milvus_stats = self.collection.num_entities if self.collection else 0
            
            return {
                'documents': doc_stats['count'],
                'faq': faq_stats['count'],
                'trusted_qa': trusted_qa_stats['count'],
                'generated_qa': {
                    'total': generated_qa_stats['total'],
                    'verified': generated_qa_stats['verified'],
                    'rejected': generated_qa_stats['rejected'],
                    'pending': generated_qa_stats['pending']
                },
                'vector_chunks': milvus_stats,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"获取知识库统计失败: {str(e)}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        try:
            health_status = {
                'postgresql': False,
                'milvus': False,
                'embedding_model': False
            }
            
            # 检查PostgreSQL
            try:
                async with self.db_pool.acquire() as conn:
                    await conn.fetchval("SELECT 1")
                health_status['postgresql'] = True
            except:
                pass
            
            # 检查Milvus
            try:
                if self.collection and utility.has_collection(self.collection_name):
                    health_status['milvus'] = True
            except:
                pass
            
            # 检查嵌入模型
            try:
                if self.embedding_model:
                    test_embedding = self.embedding_model.encode(["test"])
                    if len(test_embedding) > 0:
                        health_status['embedding_model'] = True
            except:
                pass
            
            return health_status
            
        except Exception as e:
            logger.error(f"健康检查失败: {str(e)}")
            return {'postgresql': False, 'milvus': False, 'embedding_model': False}
    
    async def close(self):
        """关闭连接"""
        try:
            if self.db_pool:
                await self.db_pool.close()
            
            if self.milvus_client:
                connections.disconnect("default")
            
            logger.info("知识库服务连接已关闭")
            
        except Exception as e:
            logger.error(f"关闭知识库服务连接失败: {str(e)}")