# 社保智答 / SocialWise

## 项目概述

社保智答(SocialWise)是一个基于通义千问大模型和科大讯飞语音技术的实时智能语音问答机器人，专注于社会保障与福利服务领域。

### 核心特性

- 🎤 **实时语音交互**：基于科大讯飞ASR/TTS，支持中文及方言
- 🧠 **智能问答**：通义千问大模型 + RAG检索增强生成
- 📊 **数据分离**：原始文档、FAQ、可信QA对分离存储
- 🔍 **向量检索**：Milvus向量数据库，精准匹配
- 📈 **监控告警**：Prometheus + Grafana实时监控
- 🏠 **本地部署**：完全本地化部署，数据安全可控

### 技术栈

- **后端**：FastAPI + Python 3.9+
- **数据库**：PostgreSQL + Milvus
- **AI模型**：通义千问 + 科大讯飞语音包
- **前端**：HTML5 + WebRTC + JavaScript
- **监控**：Prometheus + Grafana
- **部署**：Docker + Docker Compose

## 系统架构

### 核心特性
- 🎤 实时语音交互（科大讯飞ASR/TTS）
- 🧠 智能问答（通义千问 + RAG）
- 📊 数据分离存储（原始文档、FAQ、可信QA对）
- 🔍 向量检索（Milvus）
- 📈 系统监控（Prometheus）
- 🏠 本地部署

### 技术栈
- **前端**: HTML5 + WebRTC + JavaScript
- **后端**: FastAPI + Python 3.9+
- **数据库**: PostgreSQL + Milvus
- **AI模型**: 通义千问 + 科大讯飞语音包
- **监控**: Prometheus + Grafana
- **部署**: Docker + Docker Compose

## 快速开始

### 环境要求
- Python 3.9+
- Docker & Docker Compose
- PostgreSQL 14+
- Milvus 2.3+

### 安装步骤

1. 克隆项目
```bash
git clone <repository-url>
cd SocialWise
```

2. 配置环境变量
```bash
cp .env.example .env
# 编辑 .env 文件，填入API密钥
```

3. 启动服务
```bash
docker-compose up -d
```

4. 初始化数据库
```bash
python scripts/init_db.py
```

5. 访问应用
- Web界面: http://localhost:8000
- API文档: http://localhost:8000/docs
- 监控面板: http://localhost:3000

## 项目结构