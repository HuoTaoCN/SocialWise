"""
监控指标收集
"""

import time
import logging
from typing import Dict, Any
from fastapi import Request, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

# Prometheus指标
REQUEST_COUNT = Counter(
    'socialwise_requests_total',
    'Total number of requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'socialwise_request_duration_seconds',
    'Request duration in seconds',
    ['method', 'endpoint']
)

ACTIVE_SESSIONS = Gauge(
    'socialwise_active_sessions',
    'Number of active sessions'
)

ASR_REQUESTS = Counter(
    'socialwise_asr_requests_total',
    'Total ASR requests',
    ['status']
)

TTS_REQUESTS = Counter(
    'socialwise_tts_requests_total',
    'Total TTS requests',
    ['status']
)

QUERY_REQUESTS = Counter(
    'socialwise_query_requests_total',
    'Total query requests',
    ['intent', 'status']
)

QUERY_DURATION = Histogram(
    'socialwise_query_duration_seconds',
    'Query processing duration in seconds',
    ['intent']
)

async def metrics_middleware(request: Request, call_next):
    """监控中间件"""
    start_time = time.time()
    
    # 处理请求
    response = await call_next(request)
    
    # 计算处理时间
    process_time = time.time() - start_time
    
    # 记录指标
    method = request.method
    endpoint = request.url.path
    status = str(response.status_code)
    
    REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status).inc()
    REQUEST_DURATION.labels(method=method, endpoint=endpoint).observe(process_time)
    
    # 添加响应头
    response.headers["X-Process-Time"] = str(process_time)
    
    return response

def record_asr_request(success: bool):
    """记录ASR请求"""
    status = "success" if success else "error"
    ASR_REQUESTS.labels(status=status).inc()

def record_tts_request(success: bool):
    """记录TTS请求"""
    status = "success" if success else "error"
    TTS_REQUESTS.labels(status=status).inc()

def record_query_request(intent: str, success: bool, duration: float):
    """记录查询请求"""
    status = "success" if success else "error"
    QUERY_REQUESTS.labels(intent=intent, status=status).inc()
    QUERY_DURATION.labels(intent=intent).observe(duration)

def update_active_sessions(count: int):
    """更新活跃会话数"""
    ACTIVE_SESSIONS.set(count)

async def get_metrics():
    """获取Prometheus指标"""
    return generate_latest()