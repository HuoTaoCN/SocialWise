"""
自然语言处理服务 - 通义千问 + RAG
"""

import asyncio
import logging
from typing import Dict, List, Optional, Tuple, Any
import json
from datetime import datetime
import re

# 通义千问相关
from dashscope import Generation
import dashscope

# LangChain相关
from langchain.vectorstores import Milvus
from langchain.embeddings import DashScopeEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferWindowMemory
from langchain.schema import Document

from ..utils.config import settings
from .knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)

class NLPService:
    """自然语言处理服务"""
    
    def __init__(self):
        # 配置通义千问
        dashscope.api_key = settings.DASHSCOPE_API_KEY
        
        # 初始化嵌入模型
        self.embeddings = DashScopeEmbeddings(
            model="text-embedding-v1",
            dashscope_api_key=settings.DASHSCOPE_API_KEY
        )
        
        # 向量数据库连接
        self.vectorstore = None
        
        # 知识库服务
        self.knowledge_service = KnowledgeService()
        
        # 对话记忆
        self.memory = ConversationBufferWindowMemory(
            k=10,  # 保留最近10轮对话
            memory_key="chat_history",
            return_messages=True
        )
        
        # 文本分割器
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", "。", "！", "？", "；", "，"]
        )
        
        logger.info("通义千问NLP服务初始化完成")
    
    def check_health(self) -> bool:
        """检查服务健康状态"""
        return bool(settings.DASHSCOPE_API_KEY)
    
    async def initialize_vectorstore(self):
        """初始化向量数据库连接"""
        try:
            self.vectorstore = Milvus(
                embedding_function=self.embeddings,
                connection_args={
                    "host": settings.MILVUS_HOST,
                    "port": settings.MILVUS_PORT
                },
                collection_name="socialwise_knowledge"
            )
            logger.info("Milvus向量数据库连接成功")
            
        except Exception as e:
            logger.error(f"Milvus连接失败: {str(e)}")
            raise
    
    async def process_query(self, question: str, session_id: str, chat_history: List = None) -> Dict[str, Any]:
        """处理用户查询"""
        try:
            # 1. 意图识别和问题分类
            intent_result = await self._classify_intent(question)
            
            # 2. 根据意图选择处理策略
            if intent_result["intent"] == "trusted_qa":
                # 优先使用可信QA对
                answer_result = await self._query_trusted_qa(question)
            elif intent_result["intent"] == "faq":
                # 使用FAQ
                answer_result = await self._query_faq(question)
            else:
                # 使用RAG检索原始文档
                answer_result = await self._query_with_rag(question, chat_history or [])
            
            # 3. 后处理和优化
            final_answer = await self._post_process_answer(
                question=question,
                answer=answer_result["answer"],
                sources=answer_result.get("sources", [])
            )
            
            return {
                "answer": final_answer,
                "confidence": answer_result.get("confidence", 0.8),
                "sources": answer_result.get("sources", []),
                "intent": intent_result["intent"],
                "processing_time": answer_result.get("processing_time", 0)
            }
            
        except Exception as e:
            logger.error(f"查询处理失败: {str(e)}")
            return {
                "answer": "抱歉，我暂时无法回答您的问题，请稍后再试。",
                "confidence": 0.0,
                "sources": [],
                "intent": "error",
                "processing_time": 0
            }
    
    async def _classify_intent(self, question: str) -> Dict[str, Any]:
        """意图识别和问题分类"""
        try:
            # 使用通义千问进行意图分类
            prompt = f"""
请分析以下用户问题的意图类型，从以下类别中选择最合适的一个：

1. trusted_qa - 可以用已确认的问答对直接回答的问题
2. faq - 常见问题，可以用FAQ回答
3. document_search - 需要从文档中检索信息的复杂问题
4. calculation - 需要计算的问题（如社保缴费计算）
5. policy_inquiry - 政策咨询类问题
6. procedure_inquiry - 办事流程类问题

用户问题：{question}

请只返回类别名称，不要其他内容。
"""
            
            response = Generation.call(
                model="qwen-turbo",
                prompt=prompt,
                max_tokens=50
            )
            
            intent = response.output.text.strip().lower()
            
            # 验证意图类别
            valid_intents = ["trusted_qa", "faq", "document_search", "calculation", "policy_inquiry", "procedure_inquiry"]
            if intent not in valid_intents:
                intent = "document_search"  # 默认使用文档搜索
            
            return {
                "intent": intent,
                "confidence": 0.9
            }
            
        except Exception as e:
            logger.error(f"意图识别失败: {str(e)}")
            return {
                "intent": "document_search",
                "confidence": 0.5
            }
    
    async def _query_trusted_qa(self, question: str) -> Dict[str, Any]:
        """查询可信QA对"""
        try:
            # 从数据库查询可信QA对
            trusted_qa = await self.knowledge_service.search_trusted_qa(question, limit=3)
            
            if trusted_qa:
                # 使用最匹配的QA对
                best_match = trusted_qa[0]
                return {
                    "answer": best_match["answer"],
                    "confidence": best_match["similarity"],
                    "sources": [f"可信问答对 ID: {best_match['id']}"],
                    "processing_time": 0.1
                }
            else:
                # 如果没有匹配的可信QA对，降级到FAQ
                return await self._query_faq(question)
                
        except Exception as e:
            logger.error(f"可信QA查询失败: {str(e)}")
            return await self._query_faq(question)
    
    async def _query_faq(self, question: str) -> Dict[str, Any]:
        """查询FAQ"""
        try:
            # 从数据库查询FAQ
            faq_results = await self.knowledge_service.search_faq(question, limit=3)
            
            if faq_results:
                # 使用最匹配的FAQ
                best_match = faq_results[0]
                return {
                    "answer": best_match["answer"],
                    "confidence": best_match["similarity"],
                    "sources": [f"FAQ ID: {best_match['id']}"],
                    "processing_time": 0.2
                }
            else:
                # 如果没有匹配的FAQ，使用RAG
                return await self._query_with_rag(question, [])
                
        except Exception as e:
            logger.error(f"FAQ查询失败: {str(e)}")
            return await self._query_with_rag(question, [])
    
    async def _query_with_rag(self, question: str, chat_history: List) -> Dict[str, Any]:
        """使用RAG检索回答"""
        try:
            start_time = datetime.now()
            
            # 确保向量数据库已初始化
            if not self.vectorstore:
                await self.initialize_vectorstore()
            
            # 向量检索相关文档
            retriever = self.vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={"k": 5}
            )
            
            relevant_docs = await retriever.aget_relevant_documents(question)
            
            # 构建上下文
            context = "\n\n".join([doc.page_content for doc in relevant_docs])
            
            # 构建对话历史
            history_text = ""
            if chat_history:
                for msg in chat_history[-6:]:  # 最近3轮对话
                    role = "用户" if msg.get("role") == "user" else "助手"
                    history_text += f"{role}: {msg.get('content', '')}\n"
            
            # 构建提示词
            prompt = f"""
你是"社保智答/SocialWise"智能助手，专门回答社会保障和福利服务相关问题。

对话历史：
{history_text}

相关知识：
{context}

用户问题：{question}

请基于提供的知识回答用户问题，要求：
1. 回答准确、专业、易懂
2. 如果知识中没有相关信息，请诚实说明
3. 回答要有条理，必要时使用编号或分点
4. 语气友好、专业
5. 回答长度控制在200字以内

回答：
"""
            
            # 调用通义千问生成回答
            response = Generation.call(
                model="qwen-max",
                prompt=prompt,
                max_tokens=512,
                temperature=0.1
            )
            
            answer = response.output.text.strip()
            
            # 计算处理时间
            processing_time = (datetime.now() - start_time).total_seconds()
            
            # 提取源文档信息
            sources = []
            for doc in relevant_docs:
                if hasattr(doc, 'metadata') and doc.metadata:
                    source = doc.metadata.get('source', '未知来源')
                    sources.append(source)
            
            return {
                "answer": answer,
                "confidence": 0.8,
                "sources": list(set(sources)),  # 去重
                "processing_time": processing_time
            }
            
        except Exception as e:
            logger.error(f"RAG查询失败: {str(e)}")
            return {
                "answer": "抱歉，我暂时无法从知识库中找到相关信息来回答您的问题。",
                "confidence": 0.0,
                "sources": [],
                "processing_time": 0
            }
    
    async def _post_process_answer(self, question: str, answer: str, sources: List[str]) -> str:
        """后处理和优化回答"""
        try:
            # 1. 清理格式
            answer = re.sub(r'\n+', '\n', answer)  # 合并多个换行
            answer = answer.strip()
            
            # 2. 添加友好的开头（如果需要）
            if not any(greeting in answer[:20] for greeting in ["您好", "你好", "根据", "关于"]):
                if "查询" in question or "怎么" in question:
                    answer = f"关于您的问题，{answer}"
            
            # 3. 添加来源信息（如果有）
            if sources and len(sources) > 0:
                source_text = "、".join(sources[:3])  # 最多显示3个来源
                answer += f"\n\n参考来源：{source_text}"
            
            # 4. 添加品牌标识
            if len(answer) > 100:  # 只在较长回答中添加
                answer += "\n\n---\n💡 社保智答/SocialWise 为您服务"
            
            return answer
            
        except Exception as e:
            logger.error(f"回答后处理失败: {str(e)}")
            return answer
    
    async def generate_qa_pairs(self, document_text: str) -> List[Dict[str, str]]:
        """从文档生成问答对"""
        try:
            # 分割文档
            chunks = self.text_splitter.split_text(document_text)
            
            qa_pairs = []
            
            for chunk in chunks:
                if len(chunk.strip()) < 50:  # 跳过太短的片段
                    continue
                
                # 使用通义千问生成问答对
                prompt = f"""
基于以下社保相关文档内容，生成3-5个高质量的问答对。

文档内容：
{chunk}

要求：
1. 问题要具体、实用，是用户可能会问的
2. 答案要准确、完整，基于文档内容
3. 格式：Q: 问题\nA: 答案\n\n
4. 每个问答对之间用空行分隔

生成的问答对：
"""
                
                response = Generation.call(
                    model="qwen-max",
                    prompt=prompt,
                    max_tokens=1024,
                    temperature=0.3
                )
                
                # 解析生成的问答对
                generated_text = response.output.text.strip()
                pairs = self._parse_qa_pairs(generated_text)
                qa_pairs.extend(pairs)
            
            logger.info(f"从文档生成了 {len(qa_pairs)} 个问答对")
            return qa_pairs
            
        except Exception as e:
            logger.error(f"生成问答对失败: {str(e)}")
            return []
    
    def _parse_qa_pairs(self, text: str) -> List[Dict[str, str]]:
        """解析生成的问答对文本"""
        pairs = []
        
        try:
            # 按Q:和A:分割
            sections = re.split(r'Q:|A:', text)
            
            for i in range(1, len(sections), 2):
                if i + 1 < len(sections):
                    question = sections[i].strip()
                    answer = sections[i + 1].strip()
                    
                    if question and answer:
                        pairs.append({
                            "question": question,
                            "answer": answer,
                            "source": "generated",
                            "confidence": 0.7
                        })
            
        except Exception as e:
            logger.error(f"解析问答对失败: {str(e)}")
        
        return pairs
    
    async def evaluate_answer_quality(self, question: str, answer: str) -> Dict[str, Any]:
        """评估回答质量"""
        try:
            prompt = f"""
请评估以下问答的质量，从以下几个维度打分（1-10分）：

问题：{question}
回答：{answer}

评估维度：
1. 准确性 - 回答是否准确
2. 完整性 - 回答是否完整
3. 相关性 - 回答是否与问题相关
4. 清晰度 - 回答是否清晰易懂
5. 实用性 - 回答是否实用

请返回JSON格式：
{{"accuracy": 分数, "completeness": 分数, "relevance": 分数, "clarity": 分数, "usefulness": 分数, "overall": 总分, "feedback": "具体反馈"}}
"""
            
            response = Generation.call(
                model="qwen-turbo",
                prompt=prompt,
                max_tokens=256
            )
            
            # 解析评估结果
            result_text = response.output.text.strip()
            evaluation = json.loads(result_text)
            
            return evaluation
            
        except Exception as e:
            logger.error(f"回答质量评估失败: {str(e)}")
            return {
                "accuracy": 7,
                "completeness": 7,
                "relevance": 7,
                "clarity": 7,
                "usefulness": 7,
                "overall": 7,
                "feedback": "评估失败"
            }