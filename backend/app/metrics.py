"""
Prometheus监控指标
"""

import time
import psutil
from typing import Dict, Any
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# HTTP请求指标
http_requests_total = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)

http_request_duration_seconds = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration in seconds',
    ['method', 'endpoint']
)

# 业务指标
asr_requests_total = Counter(
    'asr_requests_total',
    'Total ASR requests',
    ['status']
)

tts_requests_total = Counter(
    'tts_requests_total',
    'Total TTS requests',
    ['status']
)

nlp_queries_total = Counter(
    'nlp_queries_total',
    'Total NLP queries',
    ['query_type', 'status']
)

nlp_query_duration_seconds = Histogram(
    'nlp_query_duration_seconds',
    'NLP query duration in seconds',
    ['query_type']
)

# 会话指标
active_sessions = Gauge(
    'active_sessions',
    'Number of active chat sessions'
)

session_duration_seconds = Histogram(
    'session_duration_seconds',
    'Chat session duration in seconds'
)

# 系统资源指标
system_memory_usage_bytes = Gauge(
    'system_memory_usage_bytes',
    'System memory usage in bytes'
)

system_cpu_usage_percent = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

# 知识库指标
knowledge_base_documents_total = Gauge(
    'knowledge_base_documents_total',
    'Total documents in knowledge base'
)

knowledge_base_faq_total = Gauge(
    'knowledge_base_faq_total',
    'Total FAQ entries'
)

knowledge_base_trusted_qa_total = Gauge(
    'knowledge_base_trusted_qa_total',
    'Total trusted QA pairs'
)

class MetricsMiddleware(BaseHTTPMiddleware):
    """Prometheus指标中间件"""
    
    async def dispatch(self, request: Request, call_next):
        # 记录请求开始时间
        start_time = time.time()
        
        # 处理请求
        response = await call_next(request)
        
        # 计算请求持续时间
        duration = time.time() - start_time
        
        # 提取路径模板（去除查询参数）
        path = request.url.path
        method = request.method
        status_code = str(response.status_code)
        
        # 更新指标
        http_requests_total.labels(
            method=method,
            endpoint=path,
            status_code=status_code
        ).inc()
        
        http_request_duration_seconds.labels(
            method=method,
            endpoint=path
        ).observe(duration)
        
        return response

def update_system_metrics():
    """更新系统资源指标"""
    try:
        # 内存使用情况
        memory = psutil.virtual_memory()
        system_memory_usage_bytes.set(memory.used)
        
        # CPU使用情况
        cpu_percent = psutil.cpu_percent(interval=1)
        system_cpu_usage_percent.set(cpu_percent)
        
    except Exception as e:
        # 忽略系统指标收集错误
        pass

def update_knowledge_base_metrics(stats: Dict[str, Any]):
    """更新知识库指标"""
    try:
        knowledge_base_documents_total.set(stats.get('documents', 0))
        knowledge_base_faq_total.set(stats.get('faq', 0))
        knowledge_base_trusted_qa_total.set(stats.get('trusted_qa', 0))
    except Exception as e:
        # 忽略指标更新错误
        pass

def get_metrics() -> str:
    """获取Prometheus格式的指标数据"""
    # 更新系统指标
    update_system_metrics()
    
    # 返回指标数据
    return generate_latest()

def get_metrics_content_type() -> str:
    """获取指标内容类型"""
    return CONTENT_TYPE_LATEST