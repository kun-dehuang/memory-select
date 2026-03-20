# memory-select

`memory-select` 现在是一个 API-only 的 FastAPI 服务，继续通过 `mem0` 访问：

- Qdrant 向量库
- Neo4j 图数据库
- Gemini 生成答案

默认目标已经切到 AWS 上的：

- Qdrant: `10.60.1.57:6333`
- Neo4j: `bolt://10.60.1.57:7687`

## 运行

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

## 主要接口

- `GET /health`
- `GET /api/v1/functions/schema`
- `POST /api/v1/memory/add`
- `POST /api/v1/memory/search`
- `POST /api/v1/memory/search-with-answer`
- `POST /api/v1/memory/search-graph`
- `GET /api/v1/memory/graph`
- `GET /api/v1/memory/count`
- `DELETE /api/v1/memory/clear`

## AWS

- 数据层部署说明: [AWS_DATASTORES_DEPLOYMENT.md](/Users/myles/Projects/Pupixel/memory-select/AWS_DATASTORES_DEPLOYMENT.md)
- API 层部署将使用单独的 EC2 + ECR 流程
