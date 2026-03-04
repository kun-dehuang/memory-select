# Memory Comparison Tool

对比 Mem0 (Standard & Graph) 和 Zep (Memory & Graph) 的工具。

## 项目结构

```
memory-select/
├── app.py                  # Streamlit 主应用
├── config.py               # 配置管理
├── models.py               # 数据模型
├── docker-compose.yml      # Docker 服务 (Qdrant + Neo4j)
├── requirements.txt        # Python 依赖
├── .env                    # 环境变量
├── .env.example           # 环境变量模板
├── core/                   # 核心模块
│   ├── __init__.py
│   ├── llm.py             # Gemini LLM 客户端
│   ├── mem0_wrapper.py    # Mem0 集成
│   └── zep_wrapper.py     # Zep 集成
├── utils/                 # 工具模块
│   ├── __init__.py
│   └── data_loader.py     # 数据加载工具
├── data/                  # 数据目录
│   └── uploads/           # 上传文件存储
└── ui/                    # UI 组件
    └── __init__.py
```

## 技术栈

- **前端**: Streamlit
- **LLM**: Gemini (Google Generative AI)
- **Mem0**: 本地 Docker (Neo4j + Qdrant)
- **Zep**: 云 API

## 快速开始

### 1. 启动 Docker 服务

```bash
docker-compose up -d
```

服务将启动：
- Qdrant (向量存储): http://localhost:6333
- Neo4j (图数据库): http://localhost:7474

### 2. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 到 `.env` 并填入 API 密钥：

```bash
cp .env.example .env
```

必需配置：
- `GEMINI_API_KEY`: Gemini API 密钥
- `ZEP_API_KEY`: Zep Cloud API 密钥 (可选)

### 4. 运行应用

```bash
streamlit run app.py
```

访问 http://localhost:8501

## 数据格式

上传的 JSON 文件应符合以下格式：

```json
[
  {
    "uid": "user_001",
    "text": "Today I went to the park with my friends.",
    "meta": {
      "timestamp": "2025-11-15",
      "category": "life_log",
      "stage": "stage_1"
    }
  }
]
```

## 功能

### 搜索对比
- 同时在多个内存系统中搜索
- 比较查询结果和性能
- 按用户过滤

### 图可视化
- 查看实体关系图
- 按用户过滤图数据

### 指标对比
- 查看各系统的内存统计
- 性能指标

## Docker 服务说明

### Qdrant
- 端口: 6333 (HTTP), 6334 (gRPC)
- 用于 Mem0 Standard 向量存储

### Neo4j
- 端口: 7474 (HTTP), 7687 (Bolt)
- 用户: neo4j / password123
- 用于 Mem0 Graph 图存储
