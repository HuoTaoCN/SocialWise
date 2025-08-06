"""
大语言模型服务 - 通义千问集成
"""
import asyncio
import json
from typing import List, Dict, Optional, Tuple
import dashscope
from dashscope import Generation, TextEmbedding
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import Milvus
from langchain.embeddings.base import Embeddings

from backend.core.config import settings
from backend.models.knowledge import TrustedQA, FAQ, DocumentChunk
from backend.core.database import SessionLocal

# 配置DashScope
dashscope.api_key = settings.DASHSCOPE_API_KEY

class QwenEmbeddings(Embeddings):
    """通义千问嵌入模型"""
    
    def __init__(self, model: str = "text-embedding-v1"):
        self.model = model
    
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """嵌入文档"""
        embeddings = []
        for text in texts:
            response = TextEmbedding.call(
                model=self.model,
                input=text
            )
            if response.status_code == 200:
                embeddings.append(response.output['embeddings'][0]['embedding'])
            else:
                raise Exception(f"嵌入生成失败: {response.message}")
        return embeddings
    
    def embed_query(self, text: str) -> List[float]:
        """嵌入查询"""
        response = TextEmbedding.call(
            model=self.model,
            input=text
        )
        if response.status_code == 200:
            return response.output['embeddings'][0]['embedding']
        else:
            raise Exception(f"查询嵌入失败: {response.message}")

class QwenLLMService:
    """通义千问服务"""
    
    def __init__(self):
        self.model = settings.QWEN_MODEL
        self.embeddings = QwenEmbeddings(settings.QWEN_EMBEDDING_MODEL)
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，"]
        )
    
    async def generate_response(
        self, 
        question: str, 
        context: str = "", 
        history: List[Dict] = None
    ) -> Tuple[str, float]:
        """生成回答"""
        try:
            # 构建提示词
            system_prompt = """你是"社保智答/SocialWise"智能助手，专门回答社会保障和福利服务相关问题。

请遵循以下原则：
1. 基于提供的上下文信息回答问题
2. 如果上下文中没有相关信息，请诚实说明
3. 回答要准确、简洁、易懂
4. 使用友好、专业的语调
5. 如需要，可以提供具体的操作步骤

上下文信息：
{context}

请回答用户的问题。"""
            
            messages = [
                {"role": "system", "content": system_prompt.format(context=context)}
            ]
            
            # 添加历史对话
            if history:
                messages.extend(history[-6:])  # 保留最近6轮对话
            
            messages.append({"role": "user", "content": question})
            
            # 调用通义千问
            response = Generation.call(
                model=self.model,
                messages=messages,
                result_format='message',
                max_tokens=512,
                temperature=0.3,
                top_p=0.8
            )
            
            if response.status_code == 200:
                answer = response.output.choices[0].message.content
                # 简单的置信度计算（基于回答长度和关键词匹配）
                confidence = min(0.9, len(answer) / 200 + 0.3)
                return answer, confidence
            else:
                raise Exception(f"LLM调用失败: {response.message}")
                
        except Exception as e:
            return f"抱歉，我暂时无法回答这个问题。错误信息：{str(e)}", 0.1
    
    async def search_knowledge(self, question: str, top_k: int = 3) -> List[Dict]:
        """搜索知识库"""
        db = SessionLocal()
        results = []
        
        try:
            # 1. 优先搜索可信QA对
            trusted_qas = db.query(TrustedQA).filter(
                TrustedQA.is_active == True,
                TrustedQA.human_verified == True
            ).all()
            
            for qa in trusted_qas:
                if self._calculate_similarity(question, qa.question) > 0.7:
                    results.append({
                        "type": "trusted_qa",
                        "question": qa.question,
                        "answer": qa.answer,
                        "confidence": 0.9,
                        "source": "可信问答对"
                    })
            
            # 2. 搜索FAQ
            if len(results) < top_k:
                faqs = db.query(FAQ).filter(FAQ.is_active == True).all()
                for faq in faqs:
                    if self._calculate_similarity(question, faq.question) > 0.6:
                        results.append({
                            "type": "faq",
                            "question": faq.question,
                            "answer": faq.answer,
                            "confidence": 0.8,
                            "source": "FAQ"
                        })
            
            # 3. 向量搜索文档片段
            if len(results) < top_k:
                try:
                    # 这里需要集成Milvus进行向量搜索
                    # 暂时使用简单的文本匹配
                    chunks = db.query(DocumentChunk).all()
                    for chunk in chunks:
                        if any(word in chunk.chunk_text for word in question.split()):
                            results.append({
                                "type": "document",
                                "content": chunk.chunk_text,
                                "confidence": 0.6,
                                "source": "文档片段"
                            })
                except Exception as e:
                    print(f"向量搜索失败: {e}")
            
            return results[:top_k]
            
        finally:
            db.close()
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """简单的文本相似度计算"""
        words1 = set(text1)
        words2 = set(text2)
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        return len(intersection) / len(union) if union else 0

# 全局LLM服务实例
llm_service = QwenLLMService()